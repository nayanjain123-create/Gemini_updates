import calendar
import json
from datetime import date
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q

from accounts.models import User
from reports.models import DailyTaskReport, DailyTaskComment, AssignedTask, TaskReallocation, TaskRemark, Notification
from compliance.models import ComplianceItem, ComplianceComment
from compliance.views import ensure_compliance_items_exist
from audit.models import AuditLog
from gemini_updates.date_utils import get_current_date, get_current_datetime

@login_required
def dashboard_index(request):
    today = get_current_date()
    current_year = today.year
    current_month = today.month

    # Active compliance period is previous month relative to today
    compliance_year = today.year - 1 if today.month == 1 else today.year
    compliance_month = 12 if today.month == 1 else today.month - 1

    # Ensure compliance items exist for active compliance month
    ensure_compliance_items_exist(compliance_year, compliance_month)

    # Common compliance metrics
    monthly_compliance = ComplianceItem.objects.filter(year=compliance_year, month=compliance_month)
    total_compliance_count = monthly_compliance.count()
    completed_compliance_count = monthly_compliance.filter(status=ComplianceItem.DONE).count()
    pending_compliance_count = monthly_compliance.filter(status=ComplianceItem.PENDING).count()
    na_compliance_count = monthly_compliance.filter(status=ComplianceItem.NOT_APPLICABLE).count()

    today_iso = today.strftime('%Y-%m-%d')
    current_now = get_current_datetime()

    # Statutory Tax Deadlines for Compliance (TDS = 7th, GSTR-1 = 11th, GSTR-3B = 20th)
    statutory_definitions = [
        {
            'type': ComplianceItem.TDS_PAYMENT,
            'name': 'TDS Payment Deposit',
            'short_name': 'TDS Payment',
            'due_day': 7,
            'penalty_info': '1.5% per month interest under Section 201(1A)',
            'icon': 'bi-cash-coin',
        },
        {
            'type': ComplianceItem.GSTR_1,
            'name': 'GSTR-1 (Outward Supplies Return)',
            'short_name': 'GSTR-1',
            'due_day': 11,
            'penalty_info': '₹50/day late fee under Section 47',
            'icon': 'bi-receipt-cutoff',
        },
        {
            'type': ComplianceItem.GSTR_3B,
            'name': 'GSTR-3B (Monthly Summary & Tax Deposit)',
            'short_name': 'GSTR-3B',
            'due_day': 20,
            'penalty_info': '₹50/day late fee + 18% p.a. interest',
            'icon': 'bi-file-earmark-ruled',
        },
    ]

    urgent_statutory_deadlines = []
    for s_def in statutory_definitions:
        due_date = date(current_year, current_month, s_def['due_day'])
        days_remaining = (due_date - today).days

        pending_items = monthly_compliance.filter(compliance_type=s_def['type'], status=ComplianceItem.PENDING)
        pending_count = pending_items.count()
        pending_companies = [item.get_company_display() for item in pending_items]
        total_companies_count = monthly_compliance.filter(compliance_type=s_def['type']).count()
        done_count = monthly_compliance.filter(compliance_type=s_def['type'], status=ComplianceItem.DONE).count()

        # Active starting 1 day before deadline (48-hour window from midnight before due date to 11:59 PM on due date)
        is_active = (0 <= days_remaining <= 1) and (pending_count > 0)

        # Color phase initial state
        if days_remaining < 0:
            color_phase = 'red'
            phase_label = 'OVERDUE'
        elif days_remaining == 0:
            color_phase = 'red'
            phase_label = 'DUE TODAY'
        elif days_remaining == 1:
            color_phase = 'yellow'
            phase_label = 'DUE TOMORROW'
        else:
            color_phase = 'normal'
            phase_label = f'{days_remaining} days left'

        target_iso = f"{due_date.isoformat()}T23:59:59"

        item_dict = {
            'type': s_def['type'],
            'name': s_def['name'],
            'short_name': s_def['short_name'],
            'due_day': s_def['due_day'],
            'due_date': due_date,
            'target_iso': target_iso,
            'days_remaining': days_remaining,
            'is_active': is_active,
            'pending_count': pending_count,
            'pending_companies': pending_companies,
            'total_companies_count': total_companies_count,
            'done_count': done_count,
            'color_phase': color_phase,
            'phase_label': phase_label,
            'penalty_info': s_def['penalty_info'],
            'icon': s_def['icon'],
        }

        if is_active:
            urgent_statutory_deadlines.append(item_dict)

    if request.user.is_boss:
        # ==================== BOSS EXECUTIVE COMMAND CENTER ====================
        active_employees = User.objects.filter(is_active=True, role=User.EMPLOYEE).order_by('full_name', 'username')
        total_active_employees = active_employees.count()

        # 1. Daily Reports Today
        today_reports = DailyTaskReport.objects.filter(report_date=today).select_related('employee')
        today_reports_map = {r.employee_id: r for r in today_reports}
        submitted_today_count = len(today_reports_map)
        pending_today_count = max(0, total_active_employees - submitted_today_count)
        submission_rate_today = round((submitted_today_count / total_active_employees * 100)) if total_active_employees > 0 else 0

        # 2. Tasks & Workflow Overview
        all_tasks = AssignedTask.objects.all()
        total_tasks_count = all_tasks.count()
        pending_tasks_count = all_tasks.filter(status=AssignedTask.PENDING).count()
        inprogress_tasks_count = all_tasks.filter(status=AssignedTask.IN_PROGRESS).count()
        waiting_approval_count = all_tasks.filter(status=AssignedTask.WAITING_APPROVAL).count()
        approved_tasks_count = all_tasks.filter(status=AssignedTask.APPROVED).count()
        reallocated_tasks_count = all_tasks.filter(is_reallocated=True).count()

        # Tasks awaiting Boss Approval (Actionable for 1-click Approval & Remarks right on Dashboard)
        tasks_awaiting_approval = AssignedTask.objects.filter(
            status=AssignedTask.WAITING_APPROVAL
        ).select_related('assigned_to', 'original_assigned_to', 'assigned_by').order_by('-completed_at')[:8]

        # 3. Employee Work & Performance Matrix (Boss's live workforce scoreboard)
        # Fetch month's daily reports count per employee
        month_reports = DailyTaskReport.objects.filter(
            report_date__year=current_year,
            report_date__month=current_month
        ).values('employee_id').annotate(count=Count('id'))
        month_reports_map = {item['employee_id']: item['count'] for item in month_reports}

        # Fetch active & completed task counts per employee
        tasks_by_emp = AssignedTask.objects.values('assigned_to_id', 'status').annotate(count=Count('id'))
        emp_task_stats = {}
        for t in tasks_by_emp:
            emp_id = t['assigned_to_id']
            if emp_id not in emp_task_stats:
                emp_task_stats[emp_id] = {'pending': 0, 'in_progress': 0, 'waiting_approval': 0, 'approved': 0, 'total': 0}
            st = t['status']
            cnt = t['count']
            if st == AssignedTask.PENDING:
                emp_task_stats[emp_id]['pending'] += cnt
            elif st == AssignedTask.IN_PROGRESS:
                emp_task_stats[emp_id]['in_progress'] += cnt
            elif st == AssignedTask.WAITING_APPROVAL:
                emp_task_stats[emp_id]['waiting_approval'] += cnt
            elif st == AssignedTask.APPROVED:
                emp_task_stats[emp_id]['approved'] += cnt
            emp_task_stats[emp_id]['total'] += cnt

        # Reallocations made by each employee
        reallocations_made = TaskReallocation.objects.values('reallocated_by_id').annotate(count=Count('id'))
        realloc_map = {item['reallocated_by_id']: item['count'] for item in reallocations_made}

        _, num_days_in_month = calendar.monthrange(current_year, current_month)

        employee_matrix = []
        for emp in active_employees:
            today_rep = today_reports_map.get(emp.id)
            stats = emp_task_stats.get(emp.id, {'pending': 0, 'in_progress': 0, 'waiting_approval': 0, 'approved': 0, 'total': 0})
            m_rep_count = month_reports_map.get(emp.id, 0)
            realloc_count = realloc_map.get(emp.id, 0)

            # Active workload: pending + in_progress + waiting_approval
            active_load = stats['pending'] + stats['in_progress'] + stats['waiting_approval']
            completion_rate = round((stats['approved'] / stats['total'] * 100)) if stats['total'] > 0 else (100 if m_rep_count > 0 else 0)

            employee_matrix.append({
                'employee': emp,
                'today_submitted': today_rep is not None,
                'today_task': today_rep,
                'active_tasks': active_load,
                'pending_tasks': stats['pending'],
                'inprogress_tasks': stats['in_progress'],
                'waiting_approval_tasks': stats['waiting_approval'],
                'approved_tasks': stats['approved'],
                'total_tasks': stats['total'],
                'reallocated_count': realloc_count,
                'monthly_reports_count': m_rep_count,
                'completion_rate': completion_rate,
            })

        # 4. Live Delegation & Task Workflow Stream
        recent_reallocations = TaskReallocation.objects.select_related(
            'task', 'reallocated_by', 'reallocated_to'
        ).order_by('-created_at')[:5]

        # 5. Recent System Activity
        ALLOWED_AUDIT_ACTIONS = [
            'DAILY_TASK_CREATED',
            'DAILY_TASK_UPDATED',
            'TASK_REALLOCATED',
            'TASK_MARKED_COMPLETED',
            'TASK_APPROVED',
            'TASK_REMARK_ADDED',
            'ASSIGNED_TASK_CREATED',
            'COMPLIANCE_ITEM_COMPLETED',
            'COMPLIANCE_MARKED_DONE',
            'COMPLIANCE_MARKED_NA',
        ]
        recent_audit_logs = AuditLog.objects.filter(action__in=ALLOWED_AUDIT_ACTIONS).select_related('user').all()[:20]


        # 6. Chart.js JSON Data ─ Task Status Pie Chart
        task_status_chart = json.dumps({
            'labels': ['Pending', 'Awaiting Approval', 'Approved'],
            'data': [pending_tasks_count, waiting_approval_count, approved_tasks_count],
            'colors': ['#F59E0B', '#A855F7', '#22C55E'],
        })

        # 7. Chart.js JSON Data ─ Per-Employee Task Bar Chart
        emp_bar_labels = [item['employee'].full_name or item['employee'].username for item in employee_matrix]
        emp_bar_chart = json.dumps({
            'labels': emp_bar_labels,
            'pending': [item['pending_tasks'] for item in employee_matrix],
            'inprogress': [item['inprogress_tasks'] for item in employee_matrix],
            'waiting': [item['waiting_approval_tasks'] for item in employee_matrix],
            'approved': [item['approved_tasks'] for item in employee_matrix],
        })

        # 8. Chart.js JSON Data ─ Daily Report Submission Bar Chart (per employee this month)
        # Elapsed days = days so far in the month (up to and including today)
        elapsed_days = today.day
        daily_bar_chart = json.dumps({
            'labels': emp_bar_labels,
            'submitted': [item['monthly_reports_count'] for item in employee_matrix],
            'not_submitted': [
                max(0, elapsed_days - item['monthly_reports_count'])
                for item in employee_matrix
            ],
            'total': [num_days_in_month for _ in employee_matrix],
            'today_submitted': [bool(item['today_submitted']) for item in employee_matrix],
        })

        # 8b. Monthly Submission Grid (rows=days, cols=employees)
        # Query all reports this month as a set of (employee_id, day) tuples
        month_all_reports = DailyTaskReport.objects.filter(
            report_date__year=current_year,
            report_date__month=current_month,
            employee__in=active_employees,
        ).values_list('employee_id', 'report_date__day')
        submitted_set = set((emp_id, day) for emp_id, day in month_all_reports)

        monthly_grid = []
        for day_num in range(1, num_days_in_month + 1):
            day_date = date(current_year, current_month, day_num)
            is_past_or_today = day_date <= today
            row = {
                'day': day_num,
                'is_past_or_today': is_past_or_today,
                'cells': [],
            }
            for emp in active_employees:
                if not is_past_or_today:
                    row['cells'].append(None)   # future — blank
                elif (emp.id, day_num) in submitted_set:
                    row['cells'].append(True)   # submitted — green
                else:
                    row['cells'].append(False)  # missed — red
            monthly_grid.append(row)

        # 9. Chart.js JSON Data ─ Compliance Pie
        compliance_chart = json.dumps({
            'labels': ['Completed', 'Pending', 'N/A'],
            'data': [completed_compliance_count, pending_compliance_count, na_compliance_count],
            'colors': ['#22C55E', '#F59E0B', '#0EA5E9'],
        })

        context = {
            'role': 'BOSS',
            'today': today,
            'current_month_name': calendar.month_name[current_month],
            'compliance_month_name': calendar.month_name[compliance_month],
            'compliance_year': compliance_year,
            'total_active_employees': total_active_employees,
            'submitted_today_count': submitted_today_count,
            'pending_today_count': pending_today_count,
            'submission_rate_today': submission_rate_today,
            'total_tasks_count': total_tasks_count,
            'pending_tasks_count': pending_tasks_count,
            'inprogress_tasks_count': inprogress_tasks_count,
            'waiting_approval_count': waiting_approval_count,
            'approved_tasks_count': approved_tasks_count,
            'reallocated_tasks_count': reallocated_tasks_count,
            'tasks_awaiting_approval': tasks_awaiting_approval,
            'employee_matrix': employee_matrix,
            'recent_reallocations': recent_reallocations,
            'total_compliance_count': total_compliance_count,
            'completed_compliance_count': completed_compliance_count,
            'pending_compliance_count': pending_compliance_count,
            'na_compliance_count': na_compliance_count,
            'recent_audit_logs': recent_audit_logs,
            'active_employees': active_employees,
            'task_status_chart': task_status_chart,
            'emp_bar_chart': emp_bar_chart,
            'daily_bar_chart': daily_bar_chart,
            'compliance_chart': compliance_chart,
            'num_days_in_month': num_days_in_month,
            'monthly_grid': monthly_grid,
            'monthly_grid_employees': list(active_employees),
            'today': today,
            'today_iso': today_iso,
            'current_now_iso': current_now.isoformat(),
            'urgent_statutory_deadlines': urgent_statutory_deadlines,
        }
    else:
        # ==================== EMPLOYEE PERSONAL COCKPIT ====================
        today_task = DailyTaskReport.objects.filter(employee=request.user, report_date=today).first()
        today_submitted = (today_task is not None)

        _, num_days_in_month = calendar.monthrange(current_year, current_month)
        user_monthly_tasks_count = DailyTaskReport.objects.filter(
            employee=request.user,
            report_date__year=current_year,
            report_date__month=current_month
        ).count()
        completion_pct = round((user_monthly_tasks_count / num_days_in_month) * 100) if num_days_in_month > 0 else 0

        # Assigned tasks for this user
        my_tasks = AssignedTask.objects.filter(assigned_to=request.user).select_related(
            'assigned_by', 'original_assigned_to'
        ).prefetch_related('reallocations', 'remarks')

        my_pending_tasks = my_tasks.filter(status=AssignedTask.PENDING)
        my_inprogress_tasks = my_tasks.filter(status=AssignedTask.IN_PROGRESS)
        my_waiting_approval_tasks = my_tasks.filter(status=AssignedTask.WAITING_APPROVAL)
        my_approved_tasks = my_tasks.filter(status=AssignedTask.APPROVED)

        # Tasks with boss remarks that need revision
        my_tasks_needing_revision = my_tasks.filter(status=AssignedTask.PENDING).exclude(boss_remark='')

        # Team Activity & Accomplishments stream for employees
        # Non-task actions (daily reports, compliance) are company-wide and visible to all.
        # Task-specific actions are private: only shown for this employee's own task activity.
        NON_TASK_ACTIONS = [
            'DAILY_TASK_CREATED',
            'DAILY_TASK_UPDATED',
            'COMPLIANCE_MARKED_DONE',
            'COMPLIANCE_MARKED_NA',
            'COMPLIANCE_ITEM_COMPLETED',
        ]
        TASK_SPECIFIC_ACTIONS = [
            'TASK_APPROVED',
            'TASK_MARKED_COMPLETED',
            'TASK_REALLOCATED',
            'ASSIGNED_TASK_CREATED',
        ]
        team_activity_logs = AuditLog.objects.filter(
            Q(action__in=NON_TASK_ACTIONS) |
            Q(action__in=TASK_SPECIFIC_ACTIONS, user=request.user)
        ).select_related('user').order_by('-created_at')[:10]

        other_employees = User.objects.filter(is_active=True, role=User.EMPLOYEE).exclude(id=request.user.id).order_by('full_name', 'username')

        context = {
            'role': 'EMPLOYEE',
            'today': today,
            'today_iso': today_iso,
            'current_now_iso': current_now.isoformat(),
            'current_month_name': calendar.month_name[current_month],
            'compliance_month_name': calendar.month_name[compliance_month],
            'compliance_year': compliance_year,
            'today_task': today_task,
            'today_submitted': today_submitted,
            'user_monthly_tasks_count': user_monthly_tasks_count,
            'num_days_in_month': num_days_in_month,
            'completion_pct': completion_pct,
            'my_tasks': my_tasks.exclude(status=AssignedTask.APPROVED)[:3],
            'my_total_tasks_count': my_tasks.count(),
            'my_pending_count': my_pending_tasks.count(),
            'my_inprogress_count': my_inprogress_tasks.count(),
            'my_waiting_approval_count': my_waiting_approval_tasks.count(),
            'my_approved_count': my_approved_tasks.count(),
            'my_tasks_needing_revision': my_tasks_needing_revision,
            'other_employees': other_employees,
            'total_compliance_count': total_compliance_count,
            'completed_compliance_count': completed_compliance_count,
            'pending_compliance_count': pending_compliance_count,
            'team_activity_logs': team_activity_logs,
            'urgent_statutory_deadlines': urgent_statutory_deadlines,
        }

    return render(request, 'dashboard/dashboard.html', context)


@login_required
def command_palette_api(request):
    """
    Universal Command Palette API — Exclusively for BOSS users.
    Supports intelligent search across:
    - Employees (Today's daily report, monthly compliances completed, assigned tasks & statuses)
    - Companies (Done vs Pending compliances for active month + completing employee)
    - "report" / "reports" / "daily" (Today's submissions vs unsubmitted employees)
    - "compliance" (Active month's 5-company compliance overview)
    - "tasks" / "approval" / "waiting" (Tasks awaiting boss sign-off & in-progress items)
    - Quick navigation & tool launches
    """
    if not request.user.is_boss:
        return JsonResponse({'error': 'Forbidden. Boss access required.'}, status=403)

    q = request.GET.get('q', '').strip()
    today = get_current_date()
    current_year = today.year
    current_month = today.month

    compliance_year = today.year - 1 if today.month == 1 else today.year
    compliance_month = 12 if today.month == 1 else today.month - 1
    ensure_compliance_items_exist(compliance_year, compliance_month)

    active_employees = User.objects.filter(is_active=True, role=User.EMPLOYEE).order_by('full_name', 'username')

    # If query is empty, return default overview & quick actions
    if not q:
        today_reports = DailyTaskReport.objects.filter(report_date=today).values_list('employee_id', flat=True)
        submitted_set = set(today_reports)
        pending_emps = [e.full_name or e.username for e in active_employees if e.id not in submitted_set]
        waiting_approval_count = AssignedTask.objects.filter(status=AssignedTask.WAITING_APPROVAL).count()

        # Aggregate 5-company compliance for default chart
        comp_chart_labels = []
        comp_chart_done = []
        comp_chart_pending = []
        for c_code, c_name in ComplianceItem.COMPANY_CHOICES:
            c_items = ComplianceItem.objects.filter(year=compliance_year, month=compliance_month, company=c_code)
            done_cnt = c_items.filter(status=ComplianceItem.DONE).count()
            pend_cnt = c_items.filter(status=ComplianceItem.PENDING).count()
            comp_chart_labels.append(c_code)
            comp_chart_done.append(done_cnt)
            comp_chart_pending.append(pend_cnt)

        # Aggregate employee workload for top employees
        emp_workload_labels = []
        emp_workload_pending = []
        emp_workload_waiting = []
        emp_workload_approved = []
        for emp in active_employees[:6]:
            emp_name = emp.full_name or emp.username
            emp_workload_labels.append(emp_name.split()[0] if emp_name else emp.username)
            emp_workload_pending.append(AssignedTask.objects.filter(assigned_to=emp, status=AssignedTask.PENDING).count())
            emp_workload_waiting.append(AssignedTask.objects.filter(assigned_to=emp, status=AssignedTask.WAITING_APPROVAL).count())
            emp_workload_approved.append(AssignedTask.objects.filter(assigned_to=emp, status=AssignedTask.APPROVED).count())

        return JsonResponse({
            'mode': 'default',
            'today': today.strftime('%A, %B %d, %Y'),
            'compliance_period': f"{calendar.month_name[compliance_month]} {compliance_year}",
            'stats': {
                'active_employees': active_employees.count(),
                'submitted_today': len(submitted_set),
                'pending_today': len(pending_emps),
                'pending_employees': pending_emps[:6],
                'waiting_approval_tasks': waiting_approval_count,
            },
            'charts': {
                'compliance': {
                    'labels': comp_chart_labels,
                    'done': comp_chart_done,
                    'pending': comp_chart_pending,
                },
                'workload': {
                    'labels': emp_workload_labels,
                    'pending': emp_workload_pending,
                    'waiting': emp_workload_waiting,
                    'approved': emp_workload_approved,
                },
                'daily_donut': {
                    'submitted': len(submitted_set),
                    'pending': len(pending_emps),
                }
            },
            'quick_suggestions': [
                {
                    'label': "Today's Daily Reports",
                    'desc': 'See who did what today & who has not submitted',
                    'query': 'report',
                    'icon': 'bi-calendar3-range-fill',
                    'badge': f"{len(submitted_set)} / {active_employees.count()} Submitted",
                    'badge_class': 'bg-success' if len(submitted_set) == active_employees.count() and active_employees.count() > 0 else 'bg-warning text-dark',
                },
                {
                    'label': 'Monthly Compliance Snapshot',
                    'desc': f"{calendar.month_name[compliance_month]} {compliance_year} statutory items across 5 companies",
                    'query': 'compliance',
                    'icon': 'bi-clipboard-check-fill',
                    'badge': '5 Companies',
                    'badge_class': 'bg-info text-white',
                },
                {
                    'label': 'Tasks & Approvals',
                    'desc': 'Review tasks waiting for Boss sign-off',
                    'query': 'tasks',
                    'icon': 'bi-hourglass-split',
                    'badge': f"{waiting_approval_count} Awaiting" if waiting_approval_count > 0 else 'All Clear',
                    'badge_class': 'bg-danger' if waiting_approval_count > 0 else 'bg-secondary',
                },
                {
                    'label': 'Company Compliances (LLP, GI, HUF, GTW, International)',
                    'desc': 'Type any company code to see Done vs Pending items',
                    'query': 'llp',
                    'icon': 'bi-building',
                    'badge': 'Company Radar',
                    'badge_class': 'bg-primary',
                },
            ],
            'employees': [{'id': e.id, 'name': e.full_name or e.username, 'username': e.username, 'query': e.username} for e in active_employees[:10]],
            'companies': [
                {'code': 'GI', 'name': 'Gemini Insights (GI)', 'query': 'gi'},
                {'code': 'LLP', 'name': 'Gemini LLP', 'query': 'llp'},
                {'code': 'HUF', 'name': 'Gemini HUF', 'query': 'huf'},
                {'code': 'INTERNATIONAL', 'name': 'Gemini International', 'query': 'international'},
                {'code': 'GTW', 'name': 'Gemini Trading (GTW)', 'query': 'gtw'},
            ],
        })

    q_lower = q.lower()

    # 1. Company Search
    company_aliases = {
        'gi': 'GI',
        'gemini insights': 'GI',
        'gemini': 'GI',
        'llp': 'LLP',
        'huf': 'HUF',
        'international': 'INTERNATIONAL',
        'inter': 'INTERNATIONAL',
        'gtw': 'GTW',
        'trading': 'GTW',
    }

    matched_company_code = None
    for alias, code in company_aliases.items():
        if q_lower == alias or q_lower == code.lower() or (len(q_lower) >= 2 and alias.startswith(q_lower)):
            matched_company_code = code
            break

    company_data = None
    if matched_company_code:
        company_items = ComplianceItem.objects.filter(
            year=compliance_year, month=compliance_month, company=matched_company_code
        ).select_related('completed_by')

        completed_list = []
        pending_list = []
        na_list = []

        for item in company_items:
            info = {
                'id': item.id,
                'compliance_type': item.get_compliance_type_display(),
                'status': item.status,
                'status_display': item.get_status_display(),
                'completed_by': (item.completed_by.full_name or item.completed_by.username) if item.completed_by else None,
                'completed_at': item.completed_at.strftime('%b %d, %Y %I:%M %p') if item.completed_at else None,
                'reference_number': item.reference_number or '',
                'remarks': item.remarks or '',
            }
            if item.status == ComplianceItem.DONE:
                completed_list.append(info)
            elif item.status == ComplianceItem.NOT_APPLICABLE:
                na_list.append(info)
            else:
                pending_list.append(info)

        company_data = {
            'code': matched_company_code,
            'name': dict(ComplianceItem.COMPANY_CHOICES).get(matched_company_code, matched_company_code),
            'month_name': calendar.month_name[compliance_month],
            'year': compliance_year,
            'total': company_items.count(),
            'completed_count': len(completed_list),
            'pending_count': len(pending_list),
            'na_count': len(na_list),
            'completed': completed_list,
            'pending': pending_list,
            'na': na_list,
            'matrix_url': f"/compliance-report/{compliance_year}/{compliance_month}/",
        }

    # 2. Daily Report Search ("report", "daily", "today", "missing")
    report_data = None
    if any(k in q_lower for k in ['report', 'daily', 'today', 'missing']):
        today_reports = DailyTaskReport.objects.filter(report_date=today).select_related('employee')
        today_rep_map = {r.employee_id: r for r in today_reports}

        submitted_list = []
        pending_list = []
        for emp in active_employees:
            r = today_rep_map.get(emp.id)
            if r:
                submitted_list.append({
                    'employee_id': emp.id,
                    'name': emp.full_name or emp.username,
                    'username': emp.username,
                    'status': r.status,
                    'status_display': r.get_status_display(),
                    'priority': r.priority,
                    'priority_display': r.get_priority_display(),
                    'task_description': r.task_description,
                    'reference_link': r.reference_link or '',
                    'comments_count': r.comments.count(),
                    'time': r.updated_at.strftime('%I:%M %p'),
                })
            else:
                pending_list.append({
                    'employee_id': emp.id,
                    'name': emp.full_name or emp.username,
                    'username': emp.username,
                    'email': emp.email,
                })

        report_data = {
            'date': today.strftime('%A, %B %d, %Y'),
            'total_employees': active_employees.count(),
            'submitted_count': len(submitted_list),
            'pending_count': len(pending_list),
            'submission_rate': round((len(submitted_list) / active_employees.count() * 100)) if active_employees.count() > 0 else 0,
            'submitted': submitted_list,
            'pending': pending_list,
            'matrix_url': '/daily-report/',
            'missing_url': '/daily-report/missing/',
        }

    # 3. Full Compliance Search ("compliance", "tax", "gst", "tds", "filing")
    compliance_data = None
    if any(k in q_lower for k in ['compliance', 'tax', 'gst', 'tds', 'filing']):
        all_comp_items = ComplianceItem.objects.filter(
            year=compliance_year, month=compliance_month
        ).select_related('completed_by')

        grouped_by_company = {}
        for c_code, c_name in ComplianceItem.COMPANY_CHOICES:
            grouped_by_company[c_code] = {
                'code': c_code,
                'name': c_name,
                'completed': [],
                'pending': [],
                'na': []
            }

        for item in all_comp_items:
            grp = grouped_by_company.get(item.company)
            if not grp:
                continue
            item_info = {
                'id': item.id,
                'type': item.get_compliance_type_display(),
                'status': item.status,
                'completed_by': (item.completed_by.full_name or item.completed_by.username) if item.completed_by else None,
                'completed_at': item.completed_at.strftime('%b %d') if item.completed_at else None,
                'reference_number': item.reference_number or '',
            }
            if item.status == ComplianceItem.DONE:
                grp['completed'].append(item_info)
            elif item.status == ComplianceItem.NOT_APPLICABLE:
                grp['na'].append(item_info)
            else:
                grp['pending'].append(item_info)

        total_cnt = all_comp_items.count()
        done_cnt = all_comp_items.filter(status=ComplianceItem.DONE).count()
        pending_cnt = all_comp_items.filter(status=ComplianceItem.PENDING).count()

        compliance_data = {
            'month_name': calendar.month_name[compliance_month],
            'year': compliance_year,
            'total': total_cnt,
            'completed_count': done_cnt,
            'pending_count': pending_cnt,
            'completion_pct': round((done_cnt / total_cnt * 100)) if total_cnt > 0 else 0,
            'companies': list(grouped_by_company.values()),
            'matrix_url': f"/compliance-report/{compliance_year}/{compliance_month}/",
        }

    # 4. Tasks Search ("task", "waiting", "approval", "approve", "assign", "allocate")
    tasks_data = None
    if any(k in q_lower for k in ['task', 'waiting', 'approval', 'approve', 'assign', 'allocate']):
        waiting_tasks = AssignedTask.objects.filter(
            status=AssignedTask.WAITING_APPROVAL
        ).select_related('assigned_to', 'original_assigned_to', 'assigned_by')[:10]

        in_progress_tasks = AssignedTask.objects.filter(
            status=AssignedTask.IN_PROGRESS
        ).select_related('assigned_to')[:8]

        tasks_data = {
            'waiting_count': waiting_tasks.count(),
            'waiting_approval': [
                {
                    'id': t.id,
                    'title': t.title,
                    'assigned_to': t.assigned_to.full_name or t.assigned_to.username,
                    'priority': t.priority,
                    'priority_display': t.get_priority_display(),
                    'completed_at': t.completed_at.strftime('%b %d, %I:%M %p') if t.completed_at else 'Recently',
                    'due_date': t.due_date.strftime('%b %d') if t.due_date else None,
                }
                for t in waiting_tasks
            ],
            'in_progress': [
                {
                    'id': t.id,
                    'title': t.title,
                    'assigned_to': t.assigned_to.full_name or t.assigned_to.username,
                    'priority': t.priority,
                    'priority_display': t.get_priority_display(),
                    'due_date': t.due_date.strftime('%b %d') if t.due_date else None,
                }
                for t in in_progress_tasks
            ],
            'tasks_url': '/tasks/',
        }

    # 5. Employee Search (Matches full_name, username, or email)
    matched_employees_data = []
    matched_emps = active_employees.filter(
        Q(full_name__icontains=q) | Q(username__icontains=q) | Q(email__icontains=q)
    )[:5]

    for emp in matched_emps:
        # A. Today's report
        today_rep = DailyTaskReport.objects.filter(employee=emp, report_date=today).first()
        today_rep_info = None
        if today_rep:
            today_rep_info = {
                'submitted': True,
                'status': today_rep.status,
                'status_display': today_rep.get_status_display(),
                'priority': today_rep.priority,
                'priority_display': today_rep.get_priority_display(),
                'task_description': today_rep.task_description,
                'reference_link': today_rep.reference_link or '',
                'comments_count': today_rep.comments.count(),
                'time': today_rep.updated_at.strftime('%I:%M %p'),
            }
        else:
            today_rep_info = {'submitted': False}

        # B. Compliance completed this month by this employee
        emp_compliances = ComplianceItem.objects.filter(
            year=compliance_year,
            month=compliance_month,
            completed_by=emp,
            status=ComplianceItem.DONE
        ).order_by('-completed_at')

        emp_comp_list = [
            {
                'id': c.id,
                'company': c.get_company_display(),
                'compliance_type': c.get_compliance_type_display(),
                'completed_at': c.completed_at.strftime('%b %d, %I:%M %p') if c.completed_at else None,
                'reference_number': c.reference_number or '',
                'remarks': c.remarks or '',
            }
            for c in emp_compliances
        ]

        # C. Tasks assigned to this employee & their status
        emp_tasks = AssignedTask.objects.filter(
            assigned_to=emp
        ).select_related('assigned_by').order_by('-created_at')[:8]

        emp_tasks_list = [
            {
                'id': t.id,
                'title': t.title,
                'priority': t.priority,
                'priority_display': t.get_priority_display(),
                'status': t.status,
                'status_display': t.get_status_display(),
                'due_date': t.due_date.strftime('%b %d, %Y') if t.due_date else 'No due date',
                'is_reallocated': t.is_reallocated,
                'created_at': t.created_at.strftime('%b %d'),
            }
            for t in emp_tasks
        ]

        matched_employees_data.append({
            'id': emp.id,
            'name': emp.full_name or emp.username,
            'username': emp.username,
            'email': emp.email,
            'phone': emp.phone_number or '',
            'today_report': today_rep_info,
            'compliances_completed': emp_comp_list,
            'compliances_count': len(emp_comp_list),
            'tasks': emp_tasks_list,
            'tasks_count': AssignedTask.objects.filter(assigned_to=emp).count(),
            'task_stats': {
                'pending': AssignedTask.objects.filter(assigned_to=emp, status=AssignedTask.PENDING).count(),
                'waiting': AssignedTask.objects.filter(assigned_to=emp, status=AssignedTask.WAITING_APPROVAL).count(),
                'approved': AssignedTask.objects.filter(assigned_to=emp, status=AssignedTask.APPROVED).count(),
            },
            'daily_report_url': f"/daily-report/?employee={emp.id}",
        })

    # Quick Navigation / Action Links matching query
    quick_nav = []
    nav_targets = [
        {'title': 'Allocate New Task', 'desc': 'Create and assign a task to any employee', 'icon': 'bi-plus-circle-fill', 'url': '/tasks/create/', 'action': 'allocate_modal'},
        {'title': 'Daily Report Matrix', 'desc': 'Monthly calendar grid of all employee reports', 'icon': 'bi-calendar3-range-fill', 'url': '/daily-report/'},
        {'title': 'Missing Reports Tracker', 'desc': 'Check unsubmitted reports by date', 'icon': 'bi-exclamation-triangle-fill', 'url': '/daily-report/missing/'},
        {'title': 'Compliance Reporting Portal', 'desc': '5-company monthly compliance matrix', 'icon': 'bi-clipboard-check-fill', 'url': f"/compliance-report/{compliance_year}/{compliance_month}/"},
        {'title': 'Employee Management', 'desc': 'Manage team, roles, and profiles', 'icon': 'bi-people-fill', 'url': '/employees/'},
        {'title': 'Sales Invoice Converter', 'desc': 'External sales invoice processing tool', 'icon': 'bi-graph-up-arrow', 'url': 'https://gemini-sales-invoice-converter.vercel.app/', 'external': True},
        {'title': 'Purchase Excel Tool', 'desc': 'External purchase excel management tool', 'icon': 'bi-bag-check-fill', 'url': 'https://geminiexcel.streamlit.app/', 'external': True},
    ]

    for item in nav_targets:
        if q_lower in item['title'].lower() or q_lower in item['desc'].lower():
            quick_nav.append(item)

    return JsonResponse({
        'mode': 'search',
        'query': q,
        'company': company_data,
        'report': report_data,
        'compliance': compliance_data,
        'tasks': tasks_data,
        'employees': matched_employees_data,
        'quick_nav': quick_nav,
    })


