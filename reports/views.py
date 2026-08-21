import calendar
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Q

from accounts.models import User
from accounts.decorators import boss_required
from audit.utils import log_action
from .models import DailyTaskReport, DailyTaskComment, AssignedTask
from .forms import DailyTaskForm, DailyTaskCommentForm, AssignedTaskForm, AssignedTaskStatusForm

@login_required
def daily_report_view(request, year=None, month=None):
    today = timezone.now().date()
    
    # Handle month/year params
    if not year or not month:
        selected_year = today.year
        selected_month = today.month
    else:
        selected_year = int(year)
        selected_month = int(month)

    # Compute number of days in selected month
    _, num_days = calendar.monthrange(selected_year, selected_month)
    days_range = list(range(1, num_days + 1))

    # Previous and Next Month calculation
    if selected_month == 1:
        prev_month = 12
        prev_year = selected_year - 1
    else:
        prev_month = selected_month - 1
        prev_year = selected_year

    if selected_month == 12:
        next_month = 1
        next_year = selected_year + 1
    else:
        next_month = selected_month + 1
        next_year = selected_year

    month_name = calendar.month_name[selected_month]

    # Fetch active employees ONLY (exclude Boss users from daily report matrix)
    employees = User.objects.filter(is_active=True, role=User.EMPLOYEE).order_by('full_name', 'username')

    # Filter parameters
    employee_filter = request.GET.get('employee', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if employee_filter:
        employees = employees.filter(id=employee_filter)

    # Query all reports for selected month/year
    start_date = date(selected_year, selected_month, 1)
    end_date = date(selected_year, selected_month, num_days)

    reports_qs = DailyTaskReport.objects.filter(
        report_date__gte=start_date,
        report_date__lte=end_date
    ).select_related('employee').prefetch_related('comments', 'comments__boss')

    if status_filter:
        reports_qs = reports_qs.filter(status=status_filter)

    # Map reports by (employee_id, day)
    report_matrix = {}
    for r in reports_qs:
        key = (r.employee_id, r.report_date.day)
        report_matrix[key] = r

    # Build structured row data for template rendering
    grid_rows = []
    for emp in employees:
        row_cells = []
        can_view_emp_comments = request.user.is_boss or (request.user.id == emp.id)
        for day in days_range:
            day_date = date(selected_year, selected_month, day)
            task = report_matrix.get((emp.id, day))
            is_editable = (request.user.id == emp.id)
            row_cells.append({
                'day': day,
                'date': day_date,
                'task': task,
                'is_editable': is_editable,
                # Privacy rule: Only Boss or the specific employee can see comment indicators
                'comment_count': (task.comments.count() if (task and can_view_emp_comments) else 0)
            })
        grid_rows.append({
            'employee': emp,
            'is_self': (request.user.id == emp.id),
            'cells': row_cells
        })

    all_active_employees = User.objects.filter(is_active=True, role=User.EMPLOYEE).order_by('full_name')

    context = {
        'selected_year': selected_year,
        'selected_month': selected_month,
        'month_name': month_name,
        'num_days': num_days,
        'days_range': days_range,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'grid_rows': grid_rows,
        'all_employees': all_active_employees,
        'employee_filter': employee_filter,
        'status_filter': status_filter,
        'today': today,
        'months_list': [(m, calendar.month_name[m]) for m in range(1, 13)],
        'years_list': list(range(today.year - 2, today.year + 3)),
    }
    return render(request, 'reports/daily_report.html', context)

@login_required
def daily_task_detail(request, task_id):
    """View task details and comments in JSON/modal."""
    task = get_object_or_404(
        DailyTaskReport.objects.select_related('employee').prefetch_related('comments', 'comments__boss'),
        id=task_id
    )
    
    # Access Rule: Non-boss employees cannot access another employee's task
    if request.user != task.employee and not request.user.is_boss:
        return JsonResponse({
            'error': 'Not Accessible',
            'detail': 'You do not have permission to view another employee\'s task details.'
        }, status=403)

    # PRIVACY RULE: Boss comments are ONLY visible to Boss users or the task owner
    can_view_comments = request.user.is_boss or (request.user == task.employee)

    comments_data = [
        {
            'id': c.id,
            'boss_name': c.boss.full_name or c.boss.username,
            'comment': c.comment,
            'created_at': c.created_at.strftime('%b %d, %Y %I:%M %p')
        }
        for c in task.comments.all()
    ] if can_view_comments else []

    data = {
        'id': task.id,
        'employee_id': task.employee.id,
        'employee_name': task.employee.full_name or task.employee.username,
        'report_date': task.report_date.strftime('%Y-%m-%d'),
        'report_date_formatted': task.report_date.strftime('%B %d, %Y'),
        'task_description': task.task_description,
        'status': task.status,
        'status_display': task.get_status_display(),
        'reference_link': task.reference_link,
        'is_editable': (request.user.id == task.employee.id),
        'can_view_comments': can_view_comments,
        'created_at': task.created_at.strftime('%b %d, %Y %I:%M %p'),
        'updated_at': task.updated_at.strftime('%b %d, %Y %I:%M %p'),
        'comments': comments_data,
    }
    return JsonResponse(data)

@login_required
def daily_task_save(request):
    """Create or update daily task entry."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    task_id = request.POST.get('task_id')
    report_date_str = request.POST.get('report_date')
    task_description = request.POST.get('task_description', '').strip()

    if not task_description:
        messages.error(request, "Task description cannot be empty.")
        return redirect(request.META.get('HTTP_REFERER', 'reports:daily_report'))

    try:
        report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        messages.error(request, "Invalid report date format.")
        return redirect(request.META.get('HTTP_REFERER', 'reports:daily_report'))

    # Determine target employee
    employee_id = request.POST.get('employee_id')
    if employee_id and request.user.is_boss:
        target_employee = get_object_or_404(User, id=employee_id)
    else:
        target_employee = request.user

    # Security check if editing existing task_id
    if task_id:
        existing_task = get_object_or_404(DailyTaskReport, id=task_id)
        if existing_task.employee != request.user and not request.user.is_boss:
            raise PermissionDenied("You are not authorized to edit another employee's daily report.")
        target_employee = existing_task.employee
        report_date = existing_task.report_date

    task, created = DailyTaskReport.objects.update_or_create(
        employee=target_employee,
        report_date=report_date,
        defaults={
            'task_description': task_description,
            'status': DailyTaskReport.COMPLETED,
            'priority': DailyTaskReport.MEDIUM,
            'reference_link': '',
        }
    )

    action_type = 'DAILY_TASK_CREATED' if created else 'DAILY_TASK_UPDATED'
    log_action(
        request.user,
        action_type,
        'DailyTaskReport',
        task.id,
        f"{'Created' if created else 'Updated'} daily task report for date {task.report_date}."
    )
    messages.success(request, f"Daily task report saved for {report_date.strftime('%b %d, %Y')}!")
    return redirect(request.META.get('HTTP_REFERER', 'reports:daily_report'))

@login_required
@boss_required
def daily_task_comment_add(request, task_id):
    """Boss-only endpoint to add a comment to a daily task."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    task = get_object_or_404(DailyTaskReport, id=task_id)
    comment_text = request.POST.get('comment', '').strip()

    if not comment_text:
        messages.error(request, "Comment cannot be blank.")
        return redirect(request.META.get('HTTP_REFERER', 'reports:daily_report'))

    comment = DailyTaskComment.objects.create(
        daily_task_report=task,
        boss=request.user,
        comment=comment_text
    )

    log_action(
        request.user,
        'DAILY_TASK_COMMENT_ADDED',
        'DailyTaskReport',
        task.id,
        f"Added comment on task of {task.employee.username} for date {task.report_date}."
    )
    messages.success(request, "Boss comment added successfully!")
    return redirect(request.META.get('HTTP_REFERER', 'reports:daily_report'))

@login_required
@boss_required
def missing_daily_reports_view(request):
    """Boss-only view to identify employees who haven't submitted daily tasks."""
    today = timezone.now().date()
    selected_year = int(request.GET.get('year', today.year))
    selected_month = int(request.GET.get('month', today.month))

    _, num_days = calendar.monthrange(selected_year, selected_month)
    month_days = [date(selected_year, selected_month, d) for d in range(1, num_days + 1) if date(selected_year, selected_month, d) <= today]

    active_employees = User.objects.filter(is_active=True, role=User.EMPLOYEE).order_by('full_name')

    # Get all submitted reports for this month
    submitted_reports = DailyTaskReport.objects.filter(
        report_date__year=selected_year,
        report_date__month=selected_month
    ).values_list('employee_id', 'report_date')

    submitted_set = set(submitted_reports)

    missing_records = []
    for emp in active_employees:
        missing_dates = [d for d in month_days if (emp.id, d) not in submitted_set]
        if missing_dates:
            missing_records.append({
                'employee': emp,
                'missing_count': len(missing_dates),
                'missing_dates': missing_dates
            })

    context = {
        'selected_year': selected_year,
        'selected_month': selected_month,
        'month_name': calendar.month_name[selected_month],
        'missing_records': missing_records,
        'months_list': [(m, calendar.month_name[m]) for m in range(1, 13)],
        'years_list': list(range(today.year - 2, today.year + 3)),
    }
    return render(request, 'reports/missing_reports.html', context)


# ==================== ASSIGNED TASKS MODULE ====================

@login_required
def task_list_view(request):
    """Assigned Tasks tab: Boss assigns tasks with priority; Employees view and update completion status."""
    if request.user.is_boss:
        tasks = AssignedTask.objects.select_related('assigned_by', 'assigned_to').all()
    else:
        tasks = AssignedTask.objects.select_related('assigned_by', 'assigned_to').filter(assigned_to=request.user)

    # Filter parameters
    status_filter = request.GET.get('status', '').strip()
    priority_filter = request.GET.get('priority', '').strip()
    emp_filter = request.GET.get('employee', '').strip()
    q_search = request.GET.get('q', '').strip()

    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    if emp_filter and request.user.is_boss:
        tasks = tasks.filter(assigned_to_id=emp_filter)
    if q_search:
        tasks = tasks.filter(Q(title__icontains=q_search) | Q(description__icontains=q_search))

    active_employees = User.objects.filter(is_active=True).order_by('full_name')
    form = AssignedTaskForm() if request.user.is_boss else None

    # Summary counts
    total_assigned_count = tasks.count()
    pending_count = tasks.filter(status=AssignedTask.PENDING).count()
    inprogress_count = tasks.filter(status=AssignedTask.IN_PROGRESS).count()
    completed_count = tasks.filter(status=AssignedTask.COMPLETED).count()

    context = {
        'tasks': tasks,
        'form': form,
        'active_employees': active_employees,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'emp_filter': emp_filter,
        'q_search': q_search,
        'total_assigned_count': total_assigned_count,
        'pending_count': pending_count,
        'inprogress_count': inprogress_count,
        'completed_count': completed_count,
        'priority_choices': AssignedTask.PRIORITY_CHOICES,
        'status_choices': AssignedTask.STATUS_CHOICES,
    }
    return render(request, 'reports/assigned_task_list.html', context)

@login_required
@boss_required
def task_create_view(request):
    """Boss creates a new task assigned to an employee with priority."""
    if request.method != 'POST':
        return redirect('reports:task_list')

    form = AssignedTaskForm(request.POST)
    if form.is_valid():
        task = form.save(commit=False)
        task.assigned_by = request.user
        task.save()

        log_action(
            request.user,
            'ASSIGNED_TASK_CREATED',
            'AssignedTask',
            task.id,
            f"Assigned task '{task.title}' to {task.assigned_to.username} with priority {task.get_priority_display()}."
        )
        messages.success(request, f"Task '{task.title}' successfully assigned to {task.assigned_to.full_name or task.assigned_to.username}!")
    else:
        messages.error(request, "Failed to assign task. Please check form entries.")

    return redirect('reports:task_list')

@login_required
def task_status_update_view(request, task_id):
    """Employee (or Boss) updates status of assigned task (Pending -> In Progress -> Completed)."""
    if request.method != 'POST':
        return redirect('reports:task_list')

    task = get_object_or_404(AssignedTask, id=task_id)

    # Permission check: Only assigned employee or Boss can update task status
    if task.assigned_to != request.user and not request.user.is_boss:
        raise PermissionDenied("You can only update tasks assigned to you.")

    new_status = request.POST.get('status', '').strip()
    if new_status in [AssignedTask.PENDING, AssignedTask.IN_PROGRESS, AssignedTask.COMPLETED]:
        task.status = new_status
        task.save()

        log_action(
            request.user,
            'ASSIGNED_TASK_STATUS_UPDATED',
            'AssignedTask',
            task.id,
            f"Updated status of task '{task.title}' to {task.get_status_display()}."
        )
        messages.success(request, f"Status for '{task.title}' updated to {task.get_status_display()}.")

    return redirect(request.META.get('HTTP_REFERER', 'reports:task_list'))

@login_required
@boss_required
def task_edit_view(request, task_id):
    """Boss edits assigned task details and priority."""
    task = get_object_or_404(AssignedTask, id=task_id)

    if request.method == 'POST':
        form = AssignedTaskForm(request.POST, instance=task)
        if form.is_valid():
            updated_task = form.save()
            log_action(
                request.user,
                'ASSIGNED_TASK_UPDATED',
                'AssignedTask',
                updated_task.id,
                f"Updated assigned task '{updated_task.title}' details/priority."
            )
            messages.success(request, f"Assigned task '{updated_task.title}' updated.")
            return redirect('reports:task_list')
    else:
        form = AssignedTaskForm(instance=task)

    return render(request, 'reports/assigned_task_form.html', {'form': form, 'task': task})
