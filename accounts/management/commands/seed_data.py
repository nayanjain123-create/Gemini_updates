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

        # 1. Create Boss Account
        boss_user, created_boss = User.objects.get_or_create(
            username='boss',
            defaults={
                'email': 'boss@gemini.com',
                'full_name': 'Boss Administrator',
                'role': User.BOSS,
                'is_staff': True,
                'is_superuser': True,
                'phone_number': '+1-555-0199'
            }
        )
        if created_boss:
            boss_user.set_password('boss123')
            boss_user.save()
            self.stdout.write(self.style.SUCCESS("Created Boss account: boss@gemini.com / boss123"))
        else:
            self.stdout.write(self.style.WARNING("Boss account already exists."))

        # 2. Create Employee Accounts
        employees_data = [
            {'username': 'pratik', 'email': 'pratik@gemini.com', 'full_name': 'Pratik', 'phone': '+1-555-0100', 'password': 'pratik123'},
            {'username': 'emp1', 'email': 'emp1@gemini.com', 'full_name': 'Alice Johnson', 'phone': '+1-555-0101', 'password': 'emp123'},
            {'username': 'emp2', 'email': 'emp2@gemini.com', 'full_name': 'Bob Smith', 'phone': '+1-555-0102', 'password': 'emp123'},
            {'username': 'emp3', 'email': 'emp3@gemini.com', 'full_name': 'Charlie Brown', 'phone': '+1-555-0103', 'password': 'emp123'},
        ]

        created_employees = []
        for emp_info in employees_data:
            pwd = emp_info.get('password', 'emp123')
            emp, created = User.objects.get_or_create(
                username=emp_info['username'],
                defaults={
                    'email': emp_info['email'],
                    'full_name': emp_info['full_name'],
                    'role': User.EMPLOYEE,
                    'phone_number': emp_info['phone']
                }
            )
            emp.set_password(pwd)
            emp.save()
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Employee: {emp_info['username']} / {pwd}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Updated Employee password for: {emp_info['username']}"))
            created_employees.append(emp)

        # 3. Create Compliance Items for current month
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
