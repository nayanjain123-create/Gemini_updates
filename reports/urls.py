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
    path('tasks/create/', views.task_create_view, name='task_create'),
    path('tasks/<int:task_id>/status/', views.task_status_update_view, name='task_status_update'),
    path('tasks/<int:task_id>/edit/', views.task_edit_view, name='task_edit'),
]
