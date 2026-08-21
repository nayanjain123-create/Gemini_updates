from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User
from reports.models import DailyTaskReport, DailyTaskComment, AssignedTask
from compliance.models import ComplianceItem, ComplianceComment
from compliance.views import ensure_compliance_items_exist
from audit.models import AuditLog

class Command(BaseCommand):
    help = "Clears all test dummy data and leaves a single clean Boss account for production employee onboarding."

    def handle(self, *args, **options):
        self.stdout.write("Clearing test data...")

        # Delete all test entries and logs
        DailyTaskComment.objects.all().delete()
        DailyTaskReport.objects.all().delete()
        AssignedTask.objects.all().delete()
        ComplianceComment.objects.all().delete()
        ComplianceItem.objects.all().delete()
        AuditLog.objects.all().delete()

        # Delete all test employee accounts except primary 'boss'
        User.objects.exclude(username='boss').delete()

        # Create or update primary Boss account
        boss, created = User.objects.get_or_create(
            username='boss',
            defaults={
                'email': 'boss@gemini.com',
                'full_name': 'Boss Admin',
                'role': User.BOSS,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        boss.set_password('boss123')
        boss.role = User.BOSS
        boss.is_staff = True
        boss.is_superuser = True
        boss.is_active = True
        boss.full_name = boss.full_name or 'Boss Admin'
        boss.save()

        # Initialize fresh compliance items for current month
        today = timezone.now().date()
        ensure_compliance_items_exist(today.year, today.month)

        self.stdout.write(self.style.SUCCESS("Successfully cleared all test data! Fresh application state ready for live employee usage."))
        self.stdout.write(self.style.SUCCESS("Primary Boss Account: boss / boss123"))
