from django.urls import path
from . import views

urlpatterns = [
    path('daily-report/', views.daily_report_view, name='daily_report'),
    path('daily-report/<int:year>/<int:month>/', views.daily_report_view, name='daily_report_by_month'),
    path('daily-report/task/<int:task_id>/', views.daily_task_detail, name='daily_task_detail'),
    path('daily-report/save/', views.daily_task_save, name='daily_task_save'),
    path('daily-report/task/<int:task_id>/comment/', views.daily_task_comment_add, name='daily_task_comment_add'),
    path('daily-report/missing/', views.missing_daily_reports_view, name='missing_daily_reports'),
    
    # Assigned Tasks Module
    path('tasks/', views.task_list_view, name='task_list'),
    path('reports/tasks/', views.task_list_view),
    path('tasks/create/', views.task_create_view, name='task_create'),
    path('tasks/<int:task_id>/status/', views.task_status_update_view, name='task_status_update'),
    path('tasks/<int:task_id>/reallocate/', views.task_reallocate_view, name='task_reallocate'),
    path('tasks/<int:task_id>/complete/', views.task_mark_complete_view, name='task_mark_complete'),
    path('tasks/<int:task_id>/approve/', views.task_approve_view, name='task_approve'),
    path('tasks/<int:task_id>/remark/', views.task_remark_view, name='task_remark'),
    path('tasks/<int:task_id>/edit/', views.task_edit_view, name='task_edit'),
    path('tasks/<int:task_id>/delete/', views.task_delete_view, name='task_delete'),

    # Notifications
    path('notifications/<int:notification_id>/read/', views.notification_mark_read_view, name='notification_mark_read'),
    path('reports/notifications/<int:notification_id>/read/', views.notification_mark_read_view),
    path('notifications/mark-all-read/', views.notification_mark_all_read_view, name='notification_mark_all_read'),
    path('reports/notifications/mark-all-read/', views.notification_mark_all_read_view),
    path('notifications/api/latest/', views.notification_latest_api_view, name='notification_latest_api'),
    path('reports/notifications/api/latest/', views.notification_latest_api_view),
]

