from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    BOSS = 'BOSS'
    EMPLOYEE = 'EMPLOYEE'
    
    ROLE_CHOICES = [
        (BOSS, 'Boss'),
        (EMPLOYEE, 'Employee'),
    ]

    full_name = models.CharField(max_length=150, help_text="User's full display name")
    email = models.EmailField(unique=True, help_text="Email address (used for login and notifications)")
    phone_number = models.CharField(max_length=20, blank=True, default='')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=EMPLOYEE)
    is_helper = models.BooleanField(default=False, help_text="Helper role who can mark compliance items as N/A")
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_boss(self):
        return self.role == self.BOSS

    @property
    def is_employee(self):
        return self.role == self.EMPLOYEE

    def save(self, *args, **kwargs):
        # Sync is_staff and role with is_superuser for admin convenience
        if self.is_superuser:
            self.role = self.BOSS
            self.is_staff = True
        elif self.role == self.BOSS:
            self.is_staff = True
        super().save(*args, **kwargs)

    def __str__(self):
        display_name = self.full_name if self.full_name else self.username
        return f"{display_name} ({self.get_role_display()})"


class PushSubscription(models.Model):
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='push_subscriptions'
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"PushSubscription: {self.user.username} ({self.created_at.strftime('%Y-%m-%d')})"

