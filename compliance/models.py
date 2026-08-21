from django.db import models
from django.conf import settings

class ComplianceItem(models.Model):
    # Companies
    GI = 'GI'
    INTERNATIONAL = 'INTERNATIONAL'
    HUF = 'HUF'
    LLP = 'LLP'
    GWT = 'GWT'

    COMPANY_CHOICES = [
        (GI, 'GI'),
        (INTERNATIONAL, 'International'),
        (HUF, 'HUF'),
        (LLP, 'LLP'),
        (GWT, 'GWT'),
    ]

    # Compliance Types
    TDS_PAYMENT = 'TDS_PAYMENT'
    GSTR_1 = 'GSTR_1'
    GSTR_3B = 'GSTR_3B'

    COMPLIANCE_TYPE_CHOICES = [
        (TDS_PAYMENT, 'TDS Payment'),
        (GSTR_1, 'GSTR-1'),
        (GSTR_3B, 'GSTR-3B'),
    ]

    # Status
    PENDING = 'PENDING'
    DONE = 'DONE'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (DONE, 'Done'),
    ]

    company = models.CharField(max_length=20, choices=COMPANY_CHOICES)
    compliance_type = models.CharField(max_length=20, choices=COMPLIANCE_TYPE_CHOICES)
    month = models.IntegerField(help_text="Month number (1-12)")
    year = models.IntegerField(help_text="4-digit Year (e.g. 2026)")
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_compliance_items'
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True, default='')
    reference_number = models.CharField(max_length=100, blank=True, default='', help_text="Challan/Ref No.")
    document_link = models.URLField(blank=True, default='', help_text="Reference document URL")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['company', 'compliance_type']
        unique_together = ('company', 'compliance_type', 'month', 'year')

    def __str__(self):
        return f"{self.get_company_display()} - {self.get_compliance_type_display()} ({self.month}/{self.year}) - {self.get_status_display()}"

class ComplianceComment(models.Model):
    compliance_item = models.ForeignKey(
        ComplianceItem,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    boss = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='compliance_comments'
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Boss comment by {self.boss.full_name or self.boss.username} on {self.compliance_item}"
