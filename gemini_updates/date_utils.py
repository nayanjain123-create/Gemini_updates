from datetime import date, datetime, time
from django.utils import timezone
from django.conf import settings

def get_current_date():
    """Return the system simulated date if set in settings, else timezone.now().date()."""
    override = getattr(settings, 'CURRENT_DATE_OVERRIDE', None)
    if override:
        if isinstance(override, str):
            return datetime.strptime(override, '%Y-%m-%d').date()
        return override
    return timezone.now().date()

def get_current_datetime():
    """Return an aware datetime matching the simulated date and current time."""
    override = getattr(settings, 'CURRENT_DATE_OVERRIDE', None)
    if override:
        if isinstance(override, str):
            d = datetime.strptime(override, '%Y-%m-%d').date()
        else:
            d = override
        current_t = timezone.now().time()
        naive_dt = datetime.combine(d, current_t)
        return timezone.make_aware(naive_dt, timezone.get_current_timezone())
    return timezone.now()
