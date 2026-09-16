import os
import json
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse

from .models import User, PushSubscription
from .forms import LoginForm, UserCreateForm, UserEditForm, ProfileEditForm, BossEmployeePasswordResetForm
from .decorators import boss_required
from audit.utils import log_action

def ping_view(request):
    """Lightweight ping endpoint to keep Render web service active and prevent cold-start sleeping."""
    return HttpResponse("PONG", content_type="text/plain")

def manifest_view(request):
    """Serve the Web App Manifest with application/manifest+json MIME type."""
    static_url = settings.STATIC_URL.rstrip('/')
    manifest_data = {
        "name": "Gemini Insights",
        "short_name": "Gemini Insights",
        "description": "Daily reports and compliance management",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "theme_color": "#111827",
        "background_color": "#111827",
        "icons": [
            {
                "src": f"{static_url}/pwa/icons/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": f"{static_url}/pwa/icons/icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }
    return HttpResponse(
        json.dumps(manifest_data, indent=2),
        content_type="application/manifest+json"
    )

def service_worker_view(request):
    """Serve the Progressive Web App Service Worker from root origin URL."""
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'service-worker.js')
    try:
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        content = "console.warn('Service worker script unavailable');"
    response = HttpResponse(content, content_type="application/javascript")
    response['Service-Worker-Allowed'] = '/'
    return response

def offline_view(request):
    """Public offline fallback view containing no sensitive or private data."""
    return render(request, 'offline.html')


def custom_login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            remember_me = form.cleaned_data.get('remember_me', False)
            
            login(request, user)
            
            if not remember_me:
                # Browser session expires when user closes browser
                request.session.set_expiry(0)
            else:
                # 30 days session
                request.session.set_expiry(30 * 24 * 60 * 60)

            log_action(user, 'LOGIN', 'User', user.id, f"User {user.email} logged in successfully.")
            messages.success(request, f"Welcome back, {user.full_name or user.username}!")

            next_url = request.GET.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('dashboard:index')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})

@login_required
def custom_logout_view(request):
    user = request.user
    log_action(user, 'LOGOUT', 'User', user.id, f"User {user.email} logged out.")
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('accounts:login')

@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save()
            log_action(user, 'PROFILE_UPDATED', 'User', user.id, "Updated profile information.")
            messages.success(request, "Your profile details have been updated successfully.")
            return redirect('dashboard:index')
    else:
        form = ProfileEditForm(instance=request.user)

    return render(request, 'accounts/profile.html', {'form': form})

@login_required
def change_password_view(request):
    from django.contrib.auth.forms import PasswordChangeForm
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            log_action(user, 'PASSWORD_CHANGED', 'User', user.id, "Password updated successfully.")
            messages.success(request, "Your password was updated successfully!")
            return redirect('accounts:profile')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'accounts/change_password.html', {'form': form})

@login_required
@boss_required
def employee_list_view(request):
    employees = User.objects.all().order_by('-date_joined')
    
    search_query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if search_query:
        employees = employees.filter(
            Q(full_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )

    if role_filter in [User.BOSS, User.EMPLOYEE]:
        employees = employees.filter(role=role_filter)

    if status_filter == 'active':
        employees = employees.filter(is_active=True)
    elif status_filter == 'inactive':
        employees = employees.filter(is_active=False)

    paginator = Paginator(employees, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    active_boss_count = User.objects.filter(role=User.BOSS, is_active=True).count()

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'active_boss_count': active_boss_count,
    }
    return render(request, 'accounts/employee_list.html', context)

@login_required
@boss_required
def employee_create_view(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            log_action(
                request.user,
                'EMPLOYEE_CREATED',
                'User',
                user.id,
                f"Created user {user.username} ({user.email}) as {user.get_role_display()}."
            )
            messages.success(request, f"Employee '{user.full_name or user.username}' created successfully!")
            return redirect('accounts:employee_list')
    else:
        form = UserCreateForm()

    return render(request, 'accounts/employee_form.html', {'form': form, 'title': 'Employee'})

@login_required
@boss_required
def employee_edit_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=target_user)
        if form.is_valid():
            # Check if attempting to deactivate the last remaining Boss
            new_is_active = form.cleaned_data.get('is_active')
            new_role = form.cleaned_data.get('role')

            if target_user.role == User.BOSS and (not new_is_active or new_role == User.EMPLOYEE):
                active_bosses = User.objects.filter(role=User.BOSS, is_active=True).exclude(pk=target_user.pk).count()
                if active_bosses < 1:
                    messages.error(request, "Cannot demote or deactivate the last remaining active Boss in the system!")
                    return render(request, 'accounts/employee_form.html', {'form': form, 'title': f'Edit Employee: {target_user.username}', 'target_user': target_user})

            updated_user = form.save()
            log_action(
                request.user,
                'EMPLOYEE_UPDATED',
                'User',
                updated_user.id,
                f"Updated user details for {updated_user.username}."
            )
            messages.success(request, f"Details for '{updated_user.full_name or updated_user.username}' updated successfully.")
            return redirect('accounts:employee_list')
    else:
        form = UserEditForm(instance=target_user)

    return render(request, 'accounts/employee_form.html', {'form': form, 'title': f'Edit Employee: {target_user.username}', 'target_user': target_user})

@login_required
@boss_required
def employee_role_toggle_view(request, user_id):
    if request.method != 'POST':
        return redirect('accounts:employee_list')

    target_user = get_object_or_404(User, id=user_id)

    if target_user.role == User.BOSS:
        # Check demotion safety guard
        active_bosses = User.objects.filter(role=User.BOSS, is_active=True).exclude(pk=target_user.pk).count()
        if active_bosses < 1:
            messages.error(request, "Operation denied: At least one active Boss must remain in the system!")
            return redirect('accounts:employee_list')

        target_user.role = User.EMPLOYEE
        target_user.is_staff = False
        target_user.save()
        log_action(request.user, 'ROLE_CHANGED', 'User', target_user.id, f"Demoted {target_user.username} from Boss to Employee.")
        messages.success(request, f"Demoted '{target_user.full_name or target_user.username}' to Employee role.")
    else:
        target_user.role = User.BOSS
        target_user.is_staff = True
        target_user.save()
        log_action(request.user, 'ROLE_CHANGED', 'User', target_user.id, f"Promoted {target_user.username} to Boss.")
        messages.success(request, f"Promoted '{target_user.full_name or target_user.username}' to Boss role!")

    return redirect('accounts:employee_list')

@login_required
@boss_required
def employee_status_toggle_view(request, user_id):
    if request.method != 'POST':
        return redirect('accounts:employee_list')

    target_user = get_object_or_404(User, id=user_id)

    if target_user.is_active and target_user.role == User.BOSS:
        active_bosses = User.objects.filter(role=User.BOSS, is_active=True).exclude(pk=target_user.pk).count()
        if active_bosses < 1:
            messages.error(request, "Operation denied: Cannot deactivate the last remaining active Boss!")
            return redirect('accounts:employee_list')

    target_user.is_active = not target_user.is_active
    target_user.save()
    status_str = "activated" if target_user.is_active else "deactivated"
    log_action(request.user, 'STATUS_CHANGED', 'User', target_user.id, f"User {target_user.username} was {status_str}.")
    messages.success(request, f"User '{target_user.full_name or target_user.username}' was {status_str}.")

    return redirect('accounts:employee_list')

@login_required
@boss_required
def employee_helper_toggle_view(request, user_id):
    if request.method != 'POST':
        return redirect('accounts:employee_list')

    target_user = get_object_or_404(User, id=user_id)
    target_user.is_helper = not target_user.is_helper
    target_user.save()
    
    status_str = "marked as Helper" if target_user.is_helper else "removed from Helper role"
    log_action(request.user, 'HELPER_STATUS_CHANGED', 'User', target_user.id, f"User {target_user.username} was {status_str}.")
    messages.success(request, f"User '{target_user.full_name or target_user.username}' was {status_str}.")

    return redirect('accounts:employee_list')

@login_required
@boss_required
def employee_reset_password_by_boss_view(request, user_id):
    """Boss view to directly change/reset an employee's password."""
    target_user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        form = BossEmployeePasswordResetForm(request.POST)
        if form.is_valid():
            new_pass = form.cleaned_data['new_password']
            target_user.set_password(new_pass)
            target_user.save()

            log_action(
                request.user,
                'EMPLOYEE_PASSWORD_RESET_BY_BOSS',
                'User',
                target_user.id,
                f"Boss {request.user.username} reset password for employee {target_user.username}."
            )
            messages.success(request, f"Password for {target_user.full_name or target_user.username} has been changed/reset successfully!")
            return redirect('accounts:employee_list')
    else:
        form = BossEmployeePasswordResetForm()

    return render(request, 'accounts/employee_reset_password.html', {
        'form': form,
        'target_user': target_user
    })

# Custom Error Views
def custom_403_view(request, exception=None):
    return render(request, 'errors/403.html', status=403)

def custom_404_view(request, exception=None):
    return render(request, 'errors/404.html', status=404)

def custom_500_view(request):
    return render(request, 'errors/500.html', status=500)


# Web Push API Views
def push_vapid_key_view(request):
    """Return the VAPID Public Key for Web Push subscription."""
    public_key = getattr(settings, 'WEBPUSH_VAPID_PUBLIC_KEY', '')
    return JsonResponse({'publicKey': public_key})

@login_required
def push_subscribe_view(request):
    """Save or update browser Web Push subscription for the authenticated user."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    endpoint = data.get('endpoint')
    keys = data.get('keys', {})
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')

    if not endpoint or not p256dh or not auth:
        return JsonResponse({'error': 'Missing required subscription fields'}, status=400)

    sub, created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'user': request.user,
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500]
        }
    )
    return JsonResponse({'status': 'ok', 'created': created, 'id': sub.id})

@login_required
def push_unsubscribe_view(request):
    """Remove browser Web Push subscription for the authenticated user."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        endpoint = data.get('endpoint')
    except Exception:
        endpoint = request.POST.get('endpoint')

    if endpoint:
        PushSubscription.objects.filter(endpoint=endpoint, user=request.user).delete()
    return JsonResponse({'status': 'ok'})


