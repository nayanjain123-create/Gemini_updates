from .models import Notification

def notifications_processor(request):
    """Context processor providing unread notifications count and recent notifications for the logged in user.
    Also automatically purges read notifications older than 24 hours for all users.
    """
    if request.user.is_authenticated:
        # Automatically purge read notifications older than 24h
        try:
            Notification.purge_expired_read_notifications()
        except Exception:
            pass

        recent = Notification.objects.filter(recipient=request.user).select_related('sender', 'related_task').order_by('-created_at')[:8]
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        celebrate_task = request.session.pop('celebrate_completed_task', None)
        return {
            'recent_notifications': recent,
            'unread_notifications_count': unread_count,
            'celebrate_task': celebrate_task,
        }
    return {
        'recent_notifications': [],
        'unread_notifications_count': 0,
        'celebrate_task': None,
    }
