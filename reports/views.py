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
from .models import DailyTaskReport, DailyTaskComment, AssignedTask, TaskReallocation, TaskRemark, Notification
from .forms import DailyTaskForm, DailyTaskCommentForm, AssignedTaskForm, AssignedTaskStatusForm, TaskReallocationForm, TaskRemarkForm

@login_required
def daily_report_view(request, year=None, month=None):
    today = timezone.now().date()
    
    # Handle month/year params (from URL kwargs or GET query params from dropdown)
    get_year = request.GET.get('year')
    get_month = request.GET.get('month')

    is_explicit_selection = bool(get_year or get_month or year or month)

    raw_year = get_year or year
    raw_month = get_month or month

    if raw_year and raw_month:
        try:
            selected_year = int(raw_year)
            selected_month = int(raw_month)
        except (ValueError, TypeError):
            selected_year = today.year
            selected_month = today.month
    else:
        selected_year = today.year
        selected_month = today.month

    # Auto-scroll to today ONLY when the user clicks the Daily Report tab directly (no explicit month parameter passed)
    auto_scroll_today = (not is_explicit_selection) and (selected_month == today.month and selected_year == today.year)

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
        'auto_scroll_today': auto_scroll_today,
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
        'is_editable': (request.user.id == task.employee.id and not request.user.is_boss),
        'can_view_comments': can_view_comments,
        'created_at': task.created_at.strftime('%b %d, %Y %I:%M %p'),
        'updated_at': task.updated_at.strftime('%b %d, %Y %I:%M %p'),
        'comments': comments_data,
    }
    return JsonResponse(data)

@login_required
def daily_task_save(request):
    """Create or update daily task entry (Employee self-service only; Boss has strictly read-only access)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    # Boss cannot create or edit employee daily tasks
    if request.user.is_boss:
        messages.error(request, "Boss has read-only access to employee daily tasks.")
        return redirect(request.META.get('HTTP_REFERER', 'reports:daily_report'))

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

    target_employee = request.user

    # Security check if editing existing task_id
    if task_id:
        existing_task = get_object_or_404(DailyTaskReport, id=task_id)
        if existing_task.employee != request.user:
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
    emp_display = request.user.full_name or request.user.username
    log_action(
        request.user,
        action_type,
        'DailyTaskReport',
        task.id,
        f"{emp_display} submitted daily task report for {task.report_date.strftime('%b %d, %Y')}."
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

    # Notify employee of boss comment
    if task.employee != request.user:
        Notification.send(
            recipient=task.employee,
            sender=request.user,
            title="Boss Commented on Daily Report",
            message=f"{request.user.full_name or request.user.username} commented on your report for {task.report_date.strftime('%b %d')}: \"{comment_text}\"",
            notification_type=Notification.DAILY_REPORT_COMMENT
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
    """Assigned Tasks tab: Boss assigns tasks with priority; Employees view, reallocate, mark completed, or boss approves/remarks."""
    if request.user.is_boss:
        tasks = AssignedTask.objects.select_related(
            'assigned_by', 'assigned_to', 'original_assigned_to'
        ).prefetch_related('reallocations', 'reallocations__reallocated_by', 'reallocations__reallocated_to', 'remarks', 'remarks__boss').all()
    else:
        tasks = AssignedTask.objects.select_related(
            'assigned_by', 'assigned_to', 'original_assigned_to'
        ).prefetch_related('reallocations', 'reallocations__reallocated_by', 'reallocations__reallocated_to', 'remarks', 'remarks__boss').filter(
            Q(assigned_to=request.user) | Q(original_assigned_to=request.user) | Q(status=AssignedTask.APPROVED)
        )

    # Filter parameters
    status_filter = request.GET.get('status', '').strip()
    priority_filter = request.GET.get('priority', '').strip()
    emp_filter = request.GET.get('employee', '').strip()
    reallocated_filter = request.GET.get('reallocated', '').strip()
    q_search = request.GET.get('q', '').strip()

    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    if emp_filter and request.user.is_boss:
        tasks = tasks.filter(assigned_to_id=emp_filter)
    if reallocated_filter == '1':
        tasks = tasks.filter(is_reallocated=True)
    if q_search:
        tasks = tasks.filter(Q(title__icontains=q_search) | Q(description__icontains=q_search) | Q(reallocation_reason__icontains=q_search))

    active_employees = User.objects.filter(is_active=True, role=User.EMPLOYEE).order_by('full_name', 'username')
    form = AssignedTaskForm() if request.user.is_boss else None

    # Summary counts
    total_assigned_count = tasks.count()
    pending_count = tasks.filter(status=AssignedTask.PENDING).count()
    inprogress_count = tasks.filter(status=AssignedTask.IN_PROGRESS).count()
    waiting_approval_count = tasks.filter(status=AssignedTask.WAITING_APPROVAL).count()
    approved_count = tasks.filter(status=AssignedTask.APPROVED).count()
    reallocated_count = tasks.filter(is_reallocated=True).count()

    context = {
        'tasks': tasks,
        'form': form,
        'active_employees': active_employees,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'emp_filter': emp_filter,
        'reallocated_filter': reallocated_filter,
        'q_search': q_search,
        'total_assigned_count': total_assigned_count,
        'pending_count': pending_count,
        'inprogress_count': inprogress_count,
        'waiting_approval_count': waiting_approval_count,
        'approved_count': approved_count,
        'reallocated_count': reallocated_count,
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
        task.original_assigned_to = task.assigned_to
        task.save()

        # Send notification to assigned employee
        Notification.send(
            recipient=task.assigned_to,
            sender=request.user,
            title="New Task Allocated by Boss",
            message=f"Boss {request.user.full_name or request.user.username} allocated you a task: '{task.title}' (Priority: {task.get_priority_display()}).",
            notification_type=Notification.TASK_ASSIGNED,
            related_task=task
        )

        log_action(
            request.user,
            'ASSIGNED_TASK_CREATED',
            'AssignedTask',
            task.id,
            f"Assigned task '{task.title}' to {task.assigned_to.username} with priority {task.get_priority_display()}."
        )
        messages.success(request, f"Task '{task.title}' successfully allocated to {task.assigned_to.full_name or task.assigned_to.username}!")
    else:
        messages.error(request, "Failed to assign task. Please check form entries.")

    return redirect('reports:task_list')

@login_required
def task_reallocate_view(request, task_id):
    """Employee delegates / re-allocates their assigned task to another employee with a mandatory reason."""
    if request.method != 'POST':
        return redirect('reports:task_list')

    task = get_object_or_404(AssignedTask, id=task_id)

    # Permission check: current assigned employee or boss can reallocate
    if task.assigned_to != request.user and not request.user.is_boss:
        raise PermissionDenied("You can only re-allocate tasks that are currently assigned to you.")

    reallocate_to_id = request.POST.get('reallocate_to')
    reason = request.POST.get('reason', '').strip()

    if not reallocate_to_id or not reason:
        messages.error(request, "Please select an employee and specify the reason for reallocating this task.")
        return redirect(request.META.get('HTTP_REFERER', 'reports:task_list'))

    new_assignee = get_object_or_404(User, id=reallocate_to_id, is_active=True)

    if new_assignee == task.assigned_to:
        messages.warning(request, "Task is already assigned to this employee.")
        return redirect(request.META.get('HTTP_REFERER', 'reports:task_list'))

    old_assignee = task.assigned_to

    # Record reallocation history
    TaskReallocation.objects.create(
        task=task,
        reallocated_by=request.user,
        reallocated_to=new_assignee,
        reason=reason
    )

    # Update task details
    task.assigned_to = new_assignee
    task.is_reallocated = True
    task.reallocation_reason = reason
    if task.status == AssignedTask.WAITING_APPROVAL or task.status == AssignedTask.APPROVED:
        task.status = AssignedTask.PENDING
    task.save()

    sender_name = request.user.full_name or request.user.username
    new_assignee_name = new_assignee.full_name or new_assignee.username
    old_assignee_name = old_assignee.full_name or old_assignee.username

    # 1. Notify Boss: Task was allocated to other employee
    bosses = User.objects.filter(role=User.BOSS, is_active=True)
    for boss in bosses:
        Notification.send(
            recipient=boss,
            sender=request.user,
            title=f"Task Reallocated to {new_assignee_name}",
            message=f"Task '{task.title}' was re-allocated to {new_assignee_name} by {sender_name}. Reason: \"{reason}\"",
            notification_type=Notification.TASK_REALLOCATED,
            related_task=task
        )

    # 2. Notify New Employee: rupali allocated you a task
    Notification.send(
        recipient=new_assignee,
        sender=request.user,
        title="Task Allocated to You",
        message=f"{sender_name} allocated you a task: '{task.title}'. Reason: \"{reason}\"",
        notification_type=Notification.TASK_REALLOCATED,
        related_task=task
    )

    log_action(
        request.user,
        'TASK_REALLOCATED',
        'AssignedTask',
        task.id,
        f"Reallocated task '{task.title}' from {old_assignee_name} to {new_assignee_name}. Reason: {reason}"
    )

    messages.success(request, f"Task '{task.title}' successfully re-allocated to {new_assignee_name}. Boss and colleague notified!")
    return redirect(request.META.get('HTTP_REFERER', 'reports:task_list'))

@login_required
def task_status_update_view(request, task_id):
    """Employee updates status of assigned task (Pending <-> In Progress)."""
    if request.method != 'POST':
        return redirect('reports:task_list')

    task = get_object_or_404(AssignedTask, id=task_id)

    if task.assigned_to != request.user and not request.user.is_boss:
        raise PermissionDenied("You can only update tasks assigned to you.")

    new_status = request.POST.get('status', '').strip()
    if new_status in [AssignedTask.PENDING, AssignedTask.IN_PROGRESS]:
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
def task_mark_complete_view(request, task_id):
    """Employee marks task done -> Status switches to WAITING_APPROVAL, boss notified for approval."""
    if request.method != 'POST':
        return redirect('reports:task_list')

    task = get_object_or_404(AssignedTask, id=task_id)

    if task.assigned_to != request.user and not request.user.is_boss:
        raise PermissionDenied("You can only mark tasks assigned to you as completed.")

    task.status = AssignedTask.WAITING_APPROVAL
    task.completed_at = timezone.now()
    task.save()

    emp_name = request.user.full_name or request.user.username

    # Notify Boss that given task is completed, waiting for approval
    bosses = User.objects.filter(role=User.BOSS, is_active=True)
    for boss in bosses:
        Notification.send(
            recipient=boss,
            sender=request.user,
            title=f"Task Completed by {emp_name} (Waiting for Approval)",
            message=f"{emp_name} marked task '{task.title}' as completed. Waiting for your approval.",
            notification_type=Notification.TASK_COMPLETED_WAITING_APPROVAL,
            related_task=task
        )

    log_action(
        request.user,
        'TASK_MARKED_COMPLETED',
        'AssignedTask',
        task.id,
        f"{emp_name} marked task '{task.title}' as completed (Waiting Approval)."
    )

    messages.success(request, f"Task '{task.title}' marked as completed and submitted to Boss for approval!")
    return redirect(request.META.get('HTTP_REFERER', 'reports:task_list'))

@login_required
@boss_required
def task_approve_view(request, task_id):
    """Boss approves completed task -> Employee is notified that task is approved."""
    if request.method != 'POST':
        return redirect('reports:task_list')

    task = get_object_or_404(AssignedTask, id=task_id)

    task.status = AssignedTask.APPROVED
    task.approved_at = timezone.now()
    task.save()

    boss_name = request.user.full_name or request.user.username

    # Notify current assignee
    Notification.send(
        recipient=task.assigned_to,
        sender=request.user,
        title="Task Approved by Boss!",
        message=f"Congratulations! Your completed task '{task.title}' has been approved by {boss_name}.",
        notification_type=Notification.TASK_APPROVED,
        related_task=task
    )

    # If reallocated, also notify original assignee
    if task.original_assigned_to and task.original_assigned_to != task.assigned_to:
        Notification.send(
            recipient=task.original_assigned_to,
            sender=request.user,
            title="Delegated Task Approved",
            message=f"Task '{task.title}' (originally assigned to you, completed by {task.assigned_to.full_name or task.assigned_to.username}) has been approved by {boss_name}.",
            notification_type=Notification.TASK_APPROVED,
            related_task=task
        )

    completed_by_name = task.assigned_to.full_name or task.assigned_to.username
    log_action(
        request.user,
        'TASK_APPROVED',
        'AssignedTask',
        task.id,
        f"Task '{task.title}' completed by {completed_by_name} was approved by Boss."
    )

    messages.success(request, f"Task '{task.title}' approved successfully! Employee notified.")
    return redirect(request.META.get('HTTP_REFERER', 'reports:task_list'))

@login_required
@boss_required
def task_remark_view(request, task_id):
    """Boss remarks about incomplete task -> Employee notified, task automatically switched to PENDING."""
    if request.method != 'POST':
        return redirect('reports:task_list')

    task = get_object_or_404(AssignedTask, id=task_id)
    remark_text = request.POST.get('remark', '').strip()

    if not remark_text:
        messages.error(request, "Remark text cannot be empty.")
        return redirect(request.META.get('HTTP_REFERER', 'reports:task_list'))

    # Record remark
    TaskRemark.objects.create(
        task=task,
        boss=request.user,
        remark=remark_text
    )

    # Revert status to PENDING
    task.status = AssignedTask.PENDING
    task.boss_remark = remark_text
    task.save()

    boss_name = request.user.full_name or request.user.username

    # Notify assigned employee
    Notification.send(
        recipient=task.assigned_to,
        sender=request.user,
        title="Boss Added Remark - Revision Required",
        message=f"Boss {boss_name} added a remark on '{task.title}': \"{remark_text}\". The task has been switched to Pending for revision.",
        notification_type=Notification.TASK_REVISION_REQUESTED,
        related_task=task
    )

    log_action(
        request.user,
        'TASK_REMARK_ADDED',
        'AssignedTask',
        task.id,
        f"Boss added remark on '{task.title}': '{remark_text}'. Switched task to Pending."
    )

    messages.info(request, f"Remark sent to {task.assigned_to.full_name or task.assigned_to.username}. Task reverted to Pending for revision.")
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


# ==================== NOTIFICATIONS API & VIEWS ====================

@login_required
def notification_mark_read_view(request, notification_id):
    """Mark a single notification as read."""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=['is_read', 'read_at'])
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({'status': 'success', 'id': notification.id})
    return redirect(request.META.get('HTTP_REFERER', 'dashboard:index'))

@login_required
def notification_mark_all_read_view(request):
    """Mark all notifications for logged-in user as read."""
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now()
    )
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({'status': 'success'})
    messages.success(request, "All notifications marked as read.")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard:index'))


@login_required
def notification_latest_api_view(request):
    """
    Lightweight JSON API to poll for the latest unread notification count and
    the most recent unread notification details. Used by the browser push
    notification system in base.html.
    Returns: { unread_count, latest: { id, title, message, notification_type, created_at } | null }
    """
    unread_qs = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).select_related('sender').order_by('-created_at')

    unread_count = unread_qs.count()
    latest = unread_qs.first()

    latest_data = None
    if latest:
        latest_data = {
            'id': latest.id,
            'title': latest.title,
            'message': latest.message,
            'notification_type': latest.notification_type,
            'created_at': latest.created_at.isoformat(),
        }

    return JsonResponse({
        'unread_count': unread_count,
        'latest': latest_data,
    })
