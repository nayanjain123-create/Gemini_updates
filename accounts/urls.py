from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('ping/', views.ping_view, name='ping'),
    path('login/', views.custom_login_view, name='login'),
    path('logout/', views.custom_logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    
    # Employee Management (Boss Only)
    path('employees/', views.employee_list_view, name='employee_list'),
    path('employees/add/', views.employee_create_view, name='employee_create'),
    path('employees/<int:user_id>/edit/', views.employee_edit_view, name='employee_edit'),
    path('employees/<int:user_id>/reset-password/', views.employee_reset_password_by_boss_view, name='employee_reset_password_by_boss'),
    path('employees/<int:user_id>/role/', views.employee_role_toggle_view, name='employee_role_toggle'),
    path('employees/<int:user_id>/status/', views.employee_status_toggle_view, name='employee_status_toggle'),
    path('employees/<int:user_id>/helper/', views.employee_helper_toggle_view, name='employee_helper_toggle'),
    
    # Password Reset Flow
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        email_template_name='accounts/password_reset_email.html',
        subject_template_name='accounts/password_reset_subject.txt',
        success_url='/password-reset/done/'
    ), name='password_reset'),
    
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'
    ), name='password_reset_done'),
    
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html',
        success_url='/password-reset-complete/'
    ), name='password_reset_confirm'),
    
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),

    # Web Push Notifications
    path('push/vapid-key/', views.push_vapid_key_view, name='push_vapid_key'),
    path('push/subscribe/', views.push_subscribe_view, name='push_subscribe'),
    path('push/unsubscribe/', views.push_unsubscribe_view, name='push_unsubscribe'),
    path('push/test/', views.push_test_view, name='push_test'),
]
