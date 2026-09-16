from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, PushSubscription

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'full_name', 'email', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'date_joined')
    search_fields = ('username', 'full_name', 'email', 'phone_number')
    ordering = ('-date_joined',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Profile Info', {'fields': ('full_name', 'phone_number', 'role')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Custom Profile Info', {'fields': ('full_name', 'email', 'phone_number', 'role')}),
    )

@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'endpoint_truncated', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__full_name', 'endpoint')
    list_filter = ('created_at',)

    def endpoint_truncated(self, obj):
        return obj.endpoint[:60] + '...' if len(obj.endpoint) > 60 else obj.endpoint
    endpoint_truncated.short_description = 'Push Endpoint'
