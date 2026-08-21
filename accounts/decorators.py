from functools import wraps
from django.core.exceptions import PermissionDenied

def boss_required(view_func):
    """Decorator for views that require Boss role."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if not request.user.is_boss:
            raise PermissionDenied("Only Boss users are authorized to perform this action.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
