import calendar
from datetime import date
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from accounts.models import User
from reports.models import DailyTaskReport, DailyTaskComment
from compliance.models import ComplianceItem, ComplianceComment
from compliance.views import ensure_compliance_items_exist
from audit.models import AuditLog

@login_required
def dashboard_index(request):
    today = timezone.now().date()
    current_year = today.year
    current_month = today.month

    # Ensure compliance items exist for current month
    ensure_compliance_items_exist(current_year, current_month)

    # Common compliance metrics
    monthly_compliance = ComplianceItem.objects.filter(year=current_year, month=current_month)
    total_compliance_count = monthly_compliance.count()
    completed_compliance_count = monthly_compliance.filter(status=ComplianceItem.DONE).count()
    pending_compliance_count = monthly_compliance.filter(status=ComplianceItem.PENDING).count()

    if request.user.is_boss:
        # BOSS DASHBOARD METRICS
        total_active_employees = User.objects.filter(is_active=True).count()
        
        submitted_today_count = DailyTaskReport.objects.filter(report_date=today).count()
        pending_today_count = max(0, total_active_employees - submitted_today_count)

        ALLOWED_AUDIT_ACTIONS = [
            'DAILY_TASK_CREATED',
            'DAILY_TASK_UPDATED',
            'COMPLIANCE_ITEM_COMPLETED',
            'ASSIGNED_TASK_CREATED',
            'ASSIGNED_TASK_STATUS_UPDATED',
        ]
        recent_audit_logs = AuditLog.objects.filter(action__in=ALLOWED_AUDIT_ACTIONS).select_related('user').all()[:8]

        recent_daily_comments = DailyTaskComment.objects.select_related('boss', 'daily_task_report', 'daily_task_report__employee').order_by('-created_at')[:5]
        recent_compliance_comments = ComplianceComment.objects.select_related('boss', 'compliance_item').order_by('-created_at')[:5]

        context = {
            'role': 'BOSS',
            'today': today,
            'current_month_name': calendar.month_name[current_month],
            'total_active_employees': total_active_employees,
            'submitted_today_count': submitted_today_count,
            'pending_today_count': pending_today_count,
            'total_compliance_count': total_compliance_count,
            'completed_compliance_count': completed_compliance_count,
            'pending_compliance_count': pending_compliance_count,
            'recent_audit_logs': recent_audit_logs,
            'recent_daily_comments': recent_daily_comments,
            'recent_compliance_comments': recent_compliance_comments,
        }
    else:
        # EMPLOYEE DASHBOARD METRICS
        today_task = DailyTaskReport.objects.filter(employee=request.user, report_date=today).first()
        today_submitted = (today_task is not None)

        # Monthly task completion for user
        _, num_days_in_month = calendar.monthrange(current_year, current_month)
        
        user_monthly_tasks_count = DailyTaskReport.objects.filter(
            employee=request.user,
            report_date__year=current_year,
            report_date__month=current_month
        ).count()

        completion_pct = round((user_monthly_tasks_count / num_days_in_month) * 100) if num_days_in_month > 0 else 0

        recent_compliance_updates = ComplianceItem.objects.filter(
            year=current_year,
            month=current_month,
            status=ComplianceItem.DONE
        ).select_related('completed_by').order_by('-completed_at')[:5]

        # Comments on user's tasks
        my_task_comments = DailyTaskComment.objects.filter(
            daily_task_report__employee=request.user
        ).select_related('boss', 'daily_task_report').order_by('-created_at')[:5]

        today_iso = today.strftime('%Y-%m-%d')

        context = {
            'role': 'EMPLOYEE',
            'today': today,
            'today_iso': today_iso,
            'current_month_name': calendar.month_name[current_month],
            'today_task': today_task,
            'today_submitted': today_submitted,
            'user_monthly_tasks_count': user_monthly_tasks_count,
            'num_days_in_month': num_days_in_month,
            'completion_pct': completion_pct,
            'total_compliance_count': total_compliance_count,
            'completed_compliance_count': completed_compliance_count,
            'pending_compliance_count': pending_compliance_count,
            'recent_compliance_updates': recent_compliance_updates,
            'my_task_comments': my_task_comments,
        }

    return render(request, 'dashboard/dashboard.html', context)
