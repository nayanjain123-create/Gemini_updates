from django.urls import path
from . import views

urlpatterns = [
    path('audit-logs/', views.audit_log_list, name='audit_log_list'),
]
