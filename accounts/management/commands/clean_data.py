from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User
from reports.models import DailyTaskReport, DailyTaskComment, AssignedTask
from compliance.models import ComplianceItem, ComplianceComment
from compliance.views import ensure_compliance_items_exist
from audit.models import AuditLog

class Command(BaseCommand):
    help = "Clears all test dummy data from daily reports, compliance items, tasks, and audit logs while preserving all 7 user accounts."

    def handle(self, *args, **options):
        self.stdout.write("Clearing test data from Daily Reports and Compliance...")

        # 1. Delete all test report entries, comments, assigned tasks, and logs
        DailyTaskComment.objects.all().delete()
        DailyTaskReport.objects.all().delete()
        AssignedTask.objects.all().delete()
        ComplianceComment.objects.all().delete()
        ComplianceItem.objects.all().delete()
        AuditLog.objects.all().delete()

        # 2. Ensure only the 7 requested user accounts exist and are active
        ALLOWED_USERS = [
            ('pratik', 'pratik123', 'Pratik', User.BOSS, True, True),
            ('rachana', 'rachana123', 'Rachana', User.EMPLOYEE, False, False),
            ('rupali', 'rupali123', 'Rupali', User.EMPLOYEE, False, False),
            ('pawan', 'pawan123', 'Pawan', User.EMPLOYEE, False, False),
            ('dhaval', 'dhaval123', 'Dhaval', User.EMPLOYEE, False, False),
            ('hema', 'hema123', 'Hema', User.EMPLOYEE, False, False),
            ('kshitija', 'kshitija123', 'Kshitija', User.EMPLOYEE, False, False),
        ]

        allowed_usernames = [u[0] for u in ALLOWED_USERS]
        User.objects.exclude(username__in=allowed_usernames).delete()

        for username, pwd, full_name, role, is_staff, is_superuser in ALLOWED_USERS:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username}@gemini.com',
                    'full_name': full_name,
                    'role': role,
                }
            )
            user.full_name = full_name
            user.email = f'{username}@gemini.com'
            user.role = role
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.is_active = True
            user.set_password(pwd)
            user.save()

        # 3. Initialize fresh, pending compliance items for current month
        today = timezone.now().date()
        ensure_compliance_items_exist(today.year, today.month)

        self.stdout.write(self.style.SUCCESS("Successfully cleared daily reports, tasks, compliance history, and audit logs!"))
        self.stdout.write(self.style.SUCCESS("Fresh application state ready for live production usage with all 7 user accounts intact."))

