from django.contrib import admin
from .models import ComplianceItem, ComplianceComment

class ComplianceCommentInline(admin.TabularInline):
    model = ComplianceComment
    extra = 1

@admin.register(ComplianceItem)
class ComplianceItemAdmin(admin.ModelAdmin):
    list_display = ('year', 'month', 'company', 'compliance_type', 'status', 'completed_by', 'completed_at')
    list_filter = ('company', 'compliance_type', 'status', 'year', 'month')
    search_fields = ('company', 'compliance_type', 'reference_number', 'remarks')
    inlines = [ComplianceCommentInline]

@admin.register(ComplianceComment)
class ComplianceCommentAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'boss', 'compliance_item')
    search_fields = ('boss__full_name', 'comment')
