from .models import AuditLog

def log_action(user, action, object_type='', object_id='', details=''):
    """Utility helper to record audit trail entries safely."""
    try:
        user_obj = user if (user and getattr(user, 'is_authenticated', False)) else None
        AuditLog.objects.create(
            user=user_obj,
            action=action,
            object_type=object_type,
            object_id=str(object_id) if object_id is not None else '',
            details=details
        )
    except Exception as e:
        # Prevent audit logging failures from crashing main business logic
        print(f"Failed to record audit log: {e}")
