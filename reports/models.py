from django.db import models
from django.conf import settings

class DailyTaskReport(models.Model):
    NOT_STARTED = 'NOT_STARTED'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    BLOCKED = 'BLOCKED'

    STATUS_CHOICES = [
        (NOT_STARTED, 'Not Started'),
        (IN_PROGRESS, 'In Progress'),
        (COMPLETED, 'Completed'),
        (BLOCKED, 'Blocked'),
    ]

    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'

    PRIORITY_CHOICES = [
        (LOW, 'Low'),
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
    ]

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_reports'
    )
    report_date = models.DateField(help_text="Date for this daily task report")
    task_description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=COMPLETED)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=MEDIUM)
    reference_link = models.URLField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-report_date', 'employee__full_name']
        unique_together = ('employee', 'report_date')

    def __str__(self):
        return f"{self.employee.full_name or self.employee.username} - {self.report_date} ({self.get_status_display()})"

class DailyTaskComment(models.Model):
    daily_task_report = models.ForeignKey(
        DailyTaskReport,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    boss = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_task_comments'
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.boss.full_name or self.boss.username} on {self.daily_task_report}"

class AssignedTask(models.Model):
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    URGENT = 'URGENT'

    PRIORITY_CHOICES = [
        (LOW, 'Low'),
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
        (URGENT, 'Urgent'),
    ]

    PENDING = 'PENDING'
    IN_PROGRESS = 'IN_PROGRESS'
    WAITING_APPROVAL = 'WAITING_APPROVAL'
    APPROVED = 'APPROVED'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (IN_PROGRESS, 'In Progress'),
        (WAITING_APPROVAL, 'Waiting Approval'),
        (APPROVED, 'Approved'),
    ]

    title = models.CharField(max_length=250)
    description = models.TextField(blank=True, default='')
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assigned_tasks_created'
    )
    original_assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='originally_assigned_tasks',
        help_text="The initial employee the boss allocated this task to."
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assigned_tasks_received',
        help_text="Current employee responsible for completing the task."
    )
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=MEDIUM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    due_date = models.DateField(null=True, blank=True)
    is_reallocated = models.BooleanField(default=False, help_text="Indicates whether this task was delegated to another employee.")
    reallocation_reason = models.TextField(blank=True, default='', help_text="Latest reallocation explanation.")
    boss_remark = models.TextField(blank=True, default='', help_text="Feedback or remarks from Boss requesting revisions or noting issues.")
    completed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.original_assigned_to and self.assigned_to:
            self.original_assigned_to = self.assigned_to
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} -> {self.assigned_to.full_name or self.assigned_to.username} [{self.get_priority_display()} | {self.get_status_display()}]"


class TaskReallocation(models.Model):
    task = models.ForeignKey(
        AssignedTask,
        on_delete=models.CASCADE,
        related_name='reallocations'
    )
    reallocated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reallocations_made'
    )
    reallocated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reallocations_received'
    )
    reason = models.TextField(help_text="Reason for transferring the task to another employee.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Task '{self.task.title}' reallocated from {self.reallocated_by} to {self.reallocated_to}"


class TaskRemark(models.Model):
    task = models.ForeignKey(
        AssignedTask,
        on_delete=models.CASCADE,
        related_name='remarks'
    )
    boss = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_remarks_given'
    )
    remark = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Remark by {self.boss} on '{self.task.title}': {self.remark[:40]}"


class Notification(models.Model):
    TASK_ASSIGNED = 'TASK_ASSIGNED'
    TASK_REALLOCATED = 'TASK_REALLOCATED'
    TASK_COMPLETED_WAITING_APPROVAL = 'TASK_COMPLETED_WAITING_APPROVAL'
    TASK_APPROVED = 'TASK_APPROVED'
    TASK_REVISION_REQUESTED = 'TASK_REVISION_REQUESTED'
    DAILY_REPORT_COMMENT = 'DAILY_REPORT_COMMENT'
    GENERAL = 'GENERAL'

    NOTIFICATION_TYPE_CHOICES = [
        (TASK_ASSIGNED, 'Task Assigned'),
        (TASK_REALLOCATED, 'Task Reallocated'),
        (TASK_COMPLETED_WAITING_APPROVAL, 'Task Completed (Waiting Approval)'),
        (TASK_APPROVED, 'Task Approved'),
        (TASK_REVISION_REQUESTED, 'Task Revision Requested (Remark Added)'),
        (DAILY_REPORT_COMMENT, 'Daily Report Comment'),
        (GENERAL, 'General Notification'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications_sent'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=40, choices=NOTIFICATION_TYPE_CHOICES, default=GENERAL)
    related_task = models.ForeignKey(
        AssignedTask,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"To: {self.recipient.username} | {self.title} ({'Read' if self.is_read else 'Unread'})"

    @classmethod
    def purge_expired_read_notifications(cls):
        """Automatically delete notifications that were read over 24 hours ago, or created >24h ago and marked read."""
        from datetime import timedelta
        from django.utils import timezone
        cutoff = timezone.now() - timedelta(hours=24)
        cls.objects.filter(
            is_read=True
        ).filter(
            models.Q(read_at__lte=cutoff) |
            models.Q(read_at__isnull=True, created_at__lte=cutoff)
        ).delete()

    @classmethod
    def send(cls, recipient, title, message, sender=None, notification_type=GENERAL, related_task=None):
        if not recipient:
            return None
        notif = cls.objects.create(
            recipient=recipient,
            sender=sender,
            title=title,
            message=message,
            notification_type=notification_type,
            related_task=related_task
        )

        # Trigger Web Push notification (delivers to desktop/phone even if browser is closed)
        try:
            from accounts.webpush_utils import send_push_notification_to_user
            target_url = '/tasks/' if related_task else '/dashboard/'
            send_push_notification_to_user(
                user=recipient,
                title=title,
                body=message,
                url=target_url,
                tag=f"gemini-notif-{notif.id}"
            )
        except Exception:
            pass

        return notif

