import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from reports.models import DailyTaskReport, DailyTaskComment, AssignedTask, TaskReallocation, TaskRemark, Notification
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
        if created_boss:
            boss_user.set_password('pratik123')
            boss_user.save()
        self.stdout.write(self.style.SUCCESS("Configured Boss/Admin account: pratik"))

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
                    'is_staff': False,
                    'is_superuser': False,
                }
            )
            if created:
                emp.set_password(emp_info['password'])
                emp.save()
            created_employees.append(emp)
            self.stdout.write(self.style.SUCCESS(f"Configured Employee: {emp_info['username']}"))

        # Note: We intentionally DO NOT delete custom user accounts created by the boss.

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

        # 5. Create Sample Assigned Tasks & Delegation Scenarios matching workflow
        task1, created_t1 = AssignedTask.objects.get_or_create(
            title="Complete the returns for container 4",
            defaults={
                'description': 'Process custom clearance paperwork and file the returns for incoming container 4.',
                'assigned_by': boss_user,
                'original_assigned_to': created_employees[1], # rupali
                'assigned_to': created_employees[0], # rachana
                'priority': AssignedTask.URGENT,
                'status': AssignedTask.WAITING_APPROVAL,
                'due_date': today + timedelta(days=2),
                'is_reallocated': True,
                'reallocation_reason': 'Assigned to urgent client clearance at port, Rachana handling container 4 returns.',
                'completed_at': timezone.now() - timedelta(hours=2)
            }
        )
        if created_t1:
            # Add reallocation record
            TaskReallocation.objects.create(
                task=task1,
                reallocated_by=created_employees[1], # rupali
                reallocated_to=created_employees[0], # rachana
                reason='Assigned to urgent client clearance at port, Rachana handling container 4 returns.'
            )
            # Add notifications
            Notification.send(
                recipient=boss_user,
                sender=created_employees[1],
                title="Task Reallocated to Rachana",
                message="Task 'Complete the returns for container 4' was re-allocated to Rachana by Rupali. Reason: \"Assigned to urgent client clearance at port, Rachana handling container 4 returns.\"",
                notification_type=Notification.TASK_REALLOCATED,
                related_task=task1
            )
            Notification.send(
                recipient=created_employees[0],
                sender=created_employees[1],
                title="Task Allocated to You",
                message="Rupali allocated you a task: 'Complete the returns for container 4'. Reason: \"Assigned to urgent client clearance at port, Rachana handling container 4 returns.\"",
                notification_type=Notification.TASK_REALLOCATED,
                related_task=task1
            )
            Notification.send(
                recipient=boss_user,
                sender=created_employees[0],
                title="Task Completed (Waiting for Approval)",
                message="Rachana marked task 'Complete the returns for container 4' as completed. Waiting for your approval.",
                notification_type=Notification.TASK_COMPLETED_WAITING_APPROVAL,
                related_task=task1
            )

        # Task 2: Revision requested
        task2, created_t2 = AssignedTask.objects.get_or_create(
            title="Q3 GST Verification & Reconciliations",
            defaults={
                'description': 'Reconcile 2A/2B ledger with supplier tax invoices.',
                'assigned_by': boss_user,
                'original_assigned_to': created_employees[2], # pawan
                'assigned_to': created_employees[2],
                'priority': AssignedTask.HIGH,
                'status': AssignedTask.PENDING,
                'due_date': today + timedelta(days=4),
                'boss_remark': 'Missing August purchase ledger reconciliation. Please verify and re-submit.'
            }
        )
        if created_t2:
            TaskRemark.objects.create(
                task=task2,
                boss=boss_user,
                remark='Missing August purchase ledger reconciliation. Please verify and re-submit.'
            )
            Notification.send(
                recipient=created_employees[2],
                sender=boss_user,
                title="Boss Added Remark - Revision Required",
                message='Boss Pratik added a remark on \'Q3 GST Verification & Reconciliations\': "Missing August purchase ledger reconciliation. Please verify and re-submit.". The task has been switched to Pending for revision.',
                notification_type=Notification.TASK_REVISION_REQUESTED,
                related_task=task2
            )

        # Task 3: Approved
        task3, created_t3 = AssignedTask.objects.get_or_create(
            title="Prepare Export Compliance Filing",
            defaults={
                'description': 'File shipping bills and export compliance certificates.',
                'assigned_by': boss_user,
                'original_assigned_to': created_employees[3], # dhaval
                'assigned_to': created_employees[3],
                'priority': AssignedTask.MEDIUM,
                'status': AssignedTask.APPROVED,
                'due_date': today - timedelta(days=1),
                'completed_at': timezone.now() - timedelta(days=1),
                'approved_at': timezone.now() - timedelta(hours=5)
            }
        )
        if created_t3:
            Notification.send(
                recipient=created_employees[3],
                sender=boss_user,
                title="Task Approved by Boss!",
                message="Congratulations! Your completed task 'Prepare Export Compliance Filing' has been approved by Pratik.",
                notification_type=Notification.TASK_APPROVED,
                related_task=task3
            )

        # 6. Log audit action
        log_action(boss_user, 'SEED_DATA_EXECUTED', 'System', '0', 'Seeded initial demo accounts, assigned tasks, delegation flows, and monthly compliance records.')
        self.stdout.write(self.style.SUCCESS("Successfully completed data seeding! You can now log in."))

