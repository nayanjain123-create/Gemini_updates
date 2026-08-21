from django.contrib import admin
from .models import DailyTaskReport, DailyTaskComment, AssignedTask

class DailyTaskCommentInline(admin.TabularInline):
    model = DailyTaskComment
    extra = 1

@admin.register(DailyTaskReport)
class DailyTaskReportAdmin(admin.ModelAdmin):
    list_display = ('report_date', 'employee', 'status', 'priority', 'updated_at')
    list_filter = ('status', 'priority', 'report_date')
    search_fields = ('employee__full_name', 'employee__email', 'task_description')
    inlines = [DailyTaskCommentInline]

@admin.register(DailyTaskComment)
class DailyTaskCommentAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'boss', 'daily_task_report')
    search_fields = ('boss__full_name', 'comment')

@admin.register(AssignedTask)
class AssignedTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'assigned_to', 'assigned_by', 'priority', 'status', 'due_date', 'created_at')
    list_filter = ('priority', 'status', 'created_at')
    search_fields = ('title', 'description', 'assigned_to__full_name', 'assigned_by__full_name')
