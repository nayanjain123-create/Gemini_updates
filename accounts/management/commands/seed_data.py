import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from reports.models import DailyTaskReport, DailyTaskComment
from compliance.models import ComplianceItem, ComplianceComment
from compliance.views import ensure_compliance_items_exist
from audit.utils import log_action

class Command(BaseCommand):
    help = 'Seeds initial demonstration data (Boss, Employees, Daily Reports, Compliance Items, Comments)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting data seeding process..."))

        # Allowed users list
        ALLOWED_USERNAMES = ['pratik', 'rachana', 'rupali', 'pawan', 'dhaval', 'hema', 'kshitija']

        # 1. Create Boss / Admin Account (Pratik)
        boss_user, created_boss = User.objects.get_or_create(
            username='pratik',
            defaults={
                'email': 'pratik@gemini.com',
                'full_name': 'Pratik',
                'role': User.BOSS,
                'is_staff': True,
                'is_superuser': True,
                'phone_number': '+91-9876543210'
            }
        )
        boss_user.full_name = 'Pratik'
        boss_user.email = 'pratik@gemini.com'
        boss_user.role = User.BOSS
        boss_user.is_staff = True
        boss_user.is_superuser = True
        boss_user.set_password('pratik123')
        boss_user.save()
        self.stdout.write(self.style.SUCCESS("Configured Boss/Admin account: pratik / pratik123"))

        # 2. Create Employee Accounts
        employees_data = [
            {'username': 'rachana', 'email': 'rachana@gemini.com', 'full_name': 'Rachana', 'password': 'rachana123'},
            {'username': 'rupali', 'email': 'rupali@gemini.com', 'full_name': 'Rupali', 'password': 'rupali123'},
            {'username': 'pawan', 'email': 'pawan@gemini.com', 'full_name': 'Pawan', 'password': 'pawan123'},
            {'username': 'dhaval', 'email': 'dhaval@gemini.com', 'full_name': 'Dhaval', 'password': 'dhaval123'},
            {'username': 'hema', 'email': 'hema@gemini.com', 'full_name': 'Hema', 'password': 'hema123'},
            {'username': 'kshitija', 'email': 'kshitija@gemini.com', 'full_name': 'Kshitija', 'password': 'kshitija123'},
        ]

        created_employees = []
        for emp_info in employees_data:
            emp, created = User.objects.get_or_create(
                username=emp_info['username'],
                defaults={
                    'email': emp_info['email'],
                    'full_name': emp_info['full_name'],
                    'role': User.EMPLOYEE,
                }
            )
            emp.full_name = emp_info['full_name']
            emp.email = emp_info['email']
            emp.role = User.EMPLOYEE
            emp.is_staff = False
            emp.is_superuser = False
            emp.set_password(emp_info['password'])
            emp.save()
            created_employees.append(emp)
            self.stdout.write(self.style.SUCCESS(f"Configured Employee: {emp_info['username']} / {emp_info['password']}"))

        # 3. Delete any other users not in ALLOWED_USERNAMES
        other_users = User.objects.exclude(username__in=ALLOWED_USERNAMES)
        other_count = other_users.count()
        if other_count > 0:
            other_names = list(other_users.values_list('username', flat=True))
            other_users.delete()
            self.stdout.write(self.style.WARNING(f"Removed {other_count} old user accounts: {', '.join(other_names)}"))

        # 4. Create Compliance Items for current month
        today = timezone.now().date()
        ensure_compliance_items_exist(today.year, today.month)
        self.stdout.write(self.style.SUCCESS(f"Created/Verified 15 Compliance items for {today.strftime('%B %Y')}"))

        # Mark 2 compliance items as DONE for realistic demo
        pending_items = ComplianceItem.objects.filter(year=today.year, month=today.month, status=ComplianceItem.PENDING)
        if pending_items.count() >= 2:
            item1 = pending_items[0]
            item1.status = ComplianceItem.DONE
            item1.completed_by = created_employees[0]
            item1.completed_at = timezone.now() - timedelta(days=2)
            item1.reference_number = 'CHALLAN-994812'
            item1.remarks = 'Payment processed and verified with treasury receipt.'
            item1.save()

            item2 = pending_items[1]
            item2.status = ComplianceItem.DONE
            item2.completed_by = created_employees[1]
            item2.completed_at = timezone.now() - timedelta(days=1)
            item2.reference_number = 'GSTR-ACK-2291'
            item2.remarks = 'GSTR Return successfully filed online.'
            item2.save()

            # Add a boss comment to item1
            ComplianceComment.objects.get_or_create(
                compliance_item=item1,
                boss=boss_user,
                defaults={'comment': 'Verified receipt copy in central portal. Good work.'}
            )

        # 4. Create Sample Daily Task Reports for past 5 days
        sample_tasks = [
            ("Implemented authentication flow and user permissions module.", DailyTaskReport.COMPLETED, DailyTaskReport.HIGH),
            ("Reviewing monthly tax compliance guidelines with accounting team.", DailyTaskReport.IN_PROGRESS, DailyTaskReport.MEDIUM),
            ("Blocked waiting for API credentials from client security portal.", DailyTaskReport.BLOCKED, DailyTaskReport.HIGH),
            ("Completed customer onboarding workflow refactoring.", DailyTaskReport.COMPLETED, DailyTaskReport.MEDIUM),
            ("Planning upcoming system maintenance tasks.", DailyTaskReport.NOT_STARTED, DailyTaskReport.LOW),
        ]

        for emp in created_employees:
            for day_offset in range(5):
                report_date = today - timedelta(days=day_offset)
                desc, status, prio = random.choice(sample_tasks)
                
                report, created_rep = DailyTaskReport.objects.get_or_create(
                    employee=emp,
                    report_date=report_date,
                    defaults={
                        'task_description': desc,
                        'status': status,
                        'priority': prio,
                        'reference_link': 'https://github.com/project/tasks' if status == DailyTaskReport.COMPLETED else ''
                    }
                )
                if created_rep and day_offset == 1 and emp == created_employees[0]:
                    # Add a boss comment
                    DailyTaskComment.objects.create(
                        daily_task_report=report,
                        boss=boss_user,
                        comment="Great progress! Please ensure test cases are added for this feature."
                    )

        # 5. Log audit action
        log_action(boss_user, 'SEED_DATA_EXECUTED', 'System', '0', 'Seeded initial demo accounts and monthly compliance records.')
        self.stdout.write(self.style.SUCCESS("Successfully completed data seeding! You can now log in."))
