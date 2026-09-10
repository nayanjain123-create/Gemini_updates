from django.contrib import admin
from .models import DailyTaskReport, DailyTaskComment, AssignedTask, TaskReallocation, TaskRemark, Notification

class DailyTaskCommentInline(admin.TabularInline):
    model = DailyTaskComment
    extra = 1

class TaskReallocationInline(admin.TabularInline):
    model = TaskReallocation
    extra = 0
    readonly_fields = ('reallocated_by', 'reallocated_to', 'reason', 'created_at')

class TaskRemarkInline(admin.TabularInline):
    model = TaskRemark
    extra = 0
    readonly_fields = ('boss', 'remark', 'created_at')

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
    list_display = ('title', 'assigned_to', 'original_assigned_to', 'assigned_by', 'priority', 'status', 'is_reallocated', 'due_date', 'created_at')
    list_filter = ('priority', 'status', 'is_reallocated', 'created_at')
    search_fields = ('title', 'description', 'reallocation_reason', 'boss_remark', 'assigned_to__full_name', 'assigned_by__full_name')
    inlines = [TaskReallocationInline, TaskRemarkInline]

@admin.register(TaskReallocation)
class TaskReallocationAdmin(admin.ModelAdmin):
    list_display = ('task', 'reallocated_by', 'reallocated_to', 'created_at')
    search_fields = ('task__title', 'reallocated_by__full_name', 'reallocated_to__full_name', 'reason')

@admin.register(TaskRemark)
class TaskRemarkAdmin(admin.ModelAdmin):
    list_display = ('task', 'boss', 'created_at')
    search_fields = ('task__title', 'boss__full_name', 'remark')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'sender', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'recipient__full_name', 'sender__full_name')

