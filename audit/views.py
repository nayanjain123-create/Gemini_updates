from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from .models import AuditLog

ALLOWED_AUDIT_ACTIONS = [
    'DAILY_TASK_CREATED',
    'DAILY_TASK_UPDATED',
    'COMPLIANCE_MARKED_DONE',
    'COMPLIANCE_MARKED_NA',
    'COMPLIANCE_ITEM_COMPLETED',
    'TASK_APPROVED',
    'TASK_MARKED_COMPLETED',
    'TASK_REALLOCATED',
    'ASSIGNED_TASK_CREATED',
    'ASSIGNED_TASK_STATUS_UPDATED',
    'TASK_REMARK_ADDED',
]

@login_required
def audit_log_list(request):
    # Filter strictly to relevant task creation, completion, payment & assignment logs
    logs = AuditLog.objects.filter(action__in=ALLOWED_AUDIT_ACTIONS).select_related('user')

    
    # Filtering
    user_query = request.GET.get('user', '').strip()
    action_query = request.GET.get('action', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    search = request.GET.get('q', '').strip()

    if search:
        logs = logs.filter(
            Q(user__full_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(action__icontains=search) |
            Q(details__icontains=search) |
            Q(object_type__icontains=search)
        )

    if user_query:
        logs = logs.filter(user_id=user_query)

    if action_query:
        logs = logs.filter(action__icontains=action_query)

    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)

    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)

    paginator = Paginator(logs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get distinct action list for dropdown filtering (filtered to allowed actions)
    action_types = AuditLog.objects.filter(action__in=ALLOWED_AUDIT_ACTIONS).values_list('action', flat=True).distinct()

    context = {
        'page_obj': page_obj,
        'action_types': sorted(list(set(action_types))),
        'search': search,
        'user_query': user_query,
        'action_query': action_query,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'audit/audit_log.html', context)
