from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from reports.models import DailyTaskReport, DailyTaskComment
from compliance.models import ComplianceItem, ComplianceComment

class GeminiUpdatesPermissionsAndWorkflowTests(TestCase):
    def setUp(self):
        # Create Boss User
        self.boss = User.objects.create_user(
            username='bossuser',
            email='boss@test.com',
            password='password123',
            full_name='Boss User',
            role=User.BOSS,
            is_staff=True
        )

        # Create Employee A
        self.emp_a = User.objects.create_user(
            username='emp_a',
            email='empa@test.com',
            password='password123',
            full_name='Employee A',
            role=User.EMPLOYEE
        )

        # Create Employee B
        self.emp_b = User.objects.create_user(
            username='emp_b',
            email='empb@test.com',
            password='password123',
            full_name='Employee B',
            role=User.EMPLOYEE
        )

        self.client = Client()

    # 1. Employee cannot edit another employee's daily report.
    def test_employee_cannot_edit_another_employee_daily_report(self):
        # Create report owned by Employee B
        report_b = DailyTaskReport.objects.create(
            employee=self.emp_b,
            report_date=date.today(),
            task_description="Employee B's original work",
            status=DailyTaskReport.IN_PROGRESS
        )

        # Log in as Employee A
        self.client.login(username='emp_a', password='password123')
        
        # Employee A attempts to edit Employee B's report
        response = self.client.post(reverse('reports:daily_task_save'), {
            'task_id': report_b.id,
            'report_date': str(date.today()),
            'task_description': "Hacked by Employee A",
            'status': DailyTaskReport.COMPLETED
        })

        # Expect 403 Forbidden
        self.assertEqual(response.status_code, 403)

        # Verify DB content did NOT change
        report_b.refresh_from_db()
        self.assertEqual(report_b.task_description, "Employee B's original work")

    # 2. Employee can create and edit their own daily report.
    def test_employee_can_create_and_edit_own_daily_report(self):
        self.client.login(username='emp_a', password='password123')

        # Create own report
        response = self.client.post(reverse('reports:daily_task_save'), {
            'report_date': str(date.today()),
            'task_description': "My initial work today",
            'reference_link': "https://github.com/task/1"
        })
        self.assertEqual(response.status_code, 302)

        report = DailyTaskReport.objects.get(employee=self.emp_a, report_date=date.today())
        self.assertEqual(report.task_description, "My initial work today")

        # Edit own report
        response = self.client.post(reverse('reports:daily_task_save'), {
            'task_id': report.id,
            'report_date': str(date.today()),
            'task_description': "Updated work description",
            'reference_link': "https://github.com/task/2"
        })
        self.assertEqual(response.status_code, 302)

        report.refresh_from_db()
        self.assertEqual(report.task_description, "Updated work description")
        self.assertEqual(report.status, DailyTaskReport.COMPLETED)

    # 3. Boss can view all daily reports.
    def test_boss_can_view_all_daily_reports(self):
        DailyTaskReport.objects.create(
            employee=self.emp_a,
            report_date=date.today(),
            task_description="Task A",
            status=DailyTaskReport.COMPLETED
        )
        DailyTaskReport.objects.create(
            employee=self.emp_b,
            report_date=date.today(),
            task_description="Task B",
            status=DailyTaskReport.IN_PROGRESS
        )

        self.client.login(username='bossuser', password='password123')
        response = self.client.get(reverse('reports:daily_report'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Employee A")
        self.assertContains(response, "Employee B")

    # 4. Only Boss can add daily-task comments.
    def test_only_boss_can_add_daily_task_comments(self):
        report = DailyTaskReport.objects.create(
            employee=self.emp_a,
            report_date=date.today(),
            task_description="Task A",
            status=DailyTaskReport.COMPLETED
        )

        # Employee A tries to comment -> Should be blocked (403)
        self.client.login(username='emp_a', password='password123')
        resp_emp = self.client.post(reverse('reports:daily_task_comment_add', args=[report.id]), {
            'comment': 'Employee self comment'
        })
        self.assertEqual(resp_emp.status_code, 403)
        self.assertEqual(DailyTaskComment.objects.count(), 0)

        # Boss tries to comment -> Allowed
        self.client.login(username='bossuser', password='password123')
        resp_boss = self.client.post(reverse('reports:daily_task_comment_add', args=[report.id]), {
            'comment': 'Boss feedback'
        })
        self.assertEqual(resp_boss.status_code, 302)
        self.assertEqual(DailyTaskComment.objects.count(), 1)
        self.assertEqual(DailyTaskComment.objects.first().comment, 'Boss feedback')

    # 5. Compliance item defaults to Pending.
    def test_compliance_item_defaults_to_pending(self):
        item = ComplianceItem.objects.create(
            company=ComplianceItem.GI,
            compliance_type=ComplianceItem.TDS_PAYMENT,
            month=8,
            year=2026
        )
        self.assertEqual(item.status, ComplianceItem.PENDING)
        self.assertIsNone(item.completed_by)
        self.assertIsNone(item.completed_at)

    # 6 & 7. Any employee can mark a Pending compliance item as Done & stores original user.
    def test_any_employee_can_mark_compliance_done(self):
        item = ComplianceItem.objects.create(
            company=ComplianceItem.GI,
            compliance_type=ComplianceItem.TDS_PAYMENT,
            month=8,
            year=2026
        )

        self.client.login(username='emp_a', password='password123')
        response = self.client.post(reverse('compliance:compliance_mark_done', args=[item.id]), {
            'remarks': 'Paid via net banking'
        })
        self.assertEqual(response.status_code, 302)

        item.refresh_from_db()
        self.assertEqual(item.status, ComplianceItem.DONE)
        self.assertEqual(item.completed_by, self.emp_a)
        self.assertIsNotNone(item.completed_at)
        self.assertEqual(item.remarks, 'Paid via net banking')

    # 8. A Done compliance item cannot be marked Done again.
    def test_done_compliance_item_cannot_be_marked_done_again(self):
        item = ComplianceItem.objects.create(
            company=ComplianceItem.GI,
            compliance_type=ComplianceItem.TDS_PAYMENT,
            month=8,
            year=2026,
            status=ComplianceItem.DONE,
            completed_by=self.emp_a,
            completed_at=timezone.now(),
            remarks='Original remarks'
        )

        # Employee B attempts to mark done again
        self.client.login(username='emp_b', password='password123')
        response = self.client.post(reverse('compliance:compliance_mark_done', args=[item.id]), {
            'remarks': 'Overwrite attempt'
        })
        self.assertEqual(response.status_code, 302)

        item.refresh_from_db()
        # Ensure original user and remarks remain intact
        self.assertEqual(item.completed_by, self.emp_a)
        self.assertEqual(item.remarks, 'Original remarks')

    # 8b. Helper employee can mark compliance item as N/A, Boss has view-only access.
    def test_helper_permissions_for_na_compliance(self):
        item = ComplianceItem.objects.create(
            company=ComplianceItem.GI,
            compliance_type=ComplianceItem.TDS_PAYMENT,
            month=8,
            year=2026
        )

        # Standard employee attempts mark N/A -> Forbidden (403)
        self.client.login(username='emp_a', password='password123')
        resp_std = self.client.post(reverse('compliance:compliance_mark_na', args=[item.id]), {
            'remarks': 'Standard employee N/A attempt'
        })
        self.assertEqual(resp_std.status_code, 403)

        # Boss attempts mark N/A -> Forbidden (403, view-only)
        self.client.login(username='bossuser', password='password123')
        resp_boss = self.client.post(reverse('compliance:compliance_mark_na', args=[item.id]), {
            'remarks': 'Boss N/A attempt'
        })
        self.assertEqual(resp_boss.status_code, 403)

        # Promote Employee B to Helper
        self.emp_b.is_helper = True
        self.emp_b.save()

        # Helper attempts mark N/A -> Allowed (302)
        self.client.login(username='emp_b', password='password123')
        resp_helper = self.client.post(reverse('compliance:compliance_mark_na', args=[item.id]), {
            'remarks': 'Not applicable for GI this month'
        })
        self.assertEqual(resp_helper.status_code, 302)

        item.refresh_from_db()
        self.assertEqual(item.status, ComplianceItem.NOT_APPLICABLE)
        self.assertEqual(item.completed_by, self.emp_b)
        self.assertEqual(item.remarks, 'Not applicable for GI this month')

    # 8c. Boss user gets 403 when attempting mark-done (view-only access).
    def test_boss_has_view_only_compliance_access(self):
        item = ComplianceItem.objects.create(
            company=ComplianceItem.GI,
            compliance_type=ComplianceItem.TDS_PAYMENT,
            month=8,
            year=2026
        )
        self.client.login(username='bossuser', password='password123')
        resp = self.client.post(reverse('compliance:compliance_mark_done', args=[item.id]), {
            'remarks': 'Boss mark done attempt'
        })
        self.assertEqual(resp.status_code, 403)

    # 9. Employee cannot access employee-management pages.
    def test_employee_cannot_access_employee_management(self):
        self.client.login(username='emp_a', password='password123')
        
        resp_list = self.client.get(reverse('accounts:employee_list'))
        self.assertEqual(resp_list.status_code, 403)

        resp_create = self.client.get(reverse('accounts:employee_create'))
        self.assertEqual(resp_create.status_code, 403)

    # 10. Boss can create an employee and promote to Boss.
    def test_boss_can_create_and_promote_employee(self):
        self.client.login(username='bossuser', password='password123')

        # Create new employee
        response = self.client.post(reverse('accounts:employee_create'), {
            'full_name': 'New Staff',
            'username': 'newstaff',
            'email': 'newstaff@test.com',
            'phone_number': '123456',
            'role': User.EMPLOYEE,
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 302)

        new_user = User.objects.get(username='newstaff')
        self.assertEqual(new_user.role, User.EMPLOYEE)

        # Promote to Boss
        response_promote = self.client.post(reverse('accounts:employee_role_toggle', args=[new_user.id]))
        self.assertEqual(response_promote.status_code, 302)

        new_user.refresh_from_db()
        self.assertTrue(new_user.is_boss)

    # 11. Boss demotion safety guard (cannot demote the last remaining active Boss).
    def test_cannot_demote_last_boss(self):
        self.client.login(username='bossuser', password='password123')

        # Attempt to demote self when no other Boss exists
        response = self.client.post(reverse('accounts:employee_role_toggle', args=[self.boss.id]))
        self.assertEqual(response.status_code, 302)

        self.boss.refresh_from_db()
        self.assertTrue(self.boss.is_boss) # Must remain Boss

    # 12. Privacy rule: Employee B cannot view Boss comments left on Employee A's task.
    def test_boss_comments_privacy_rule(self):
        report_a = DailyTaskReport.objects.create(
            employee=self.emp_a,
            report_date=date.today(),
            task_description="Employee A work"
        )
        comment = DailyTaskComment.objects.create(
            daily_task_report=report_a,
            boss=self.boss,
            comment="Private Boss comment for Employee A"
        )

        # Log in as Employee B (different employee) -> Should get 403 Not Accessible
        self.client.login(username='emp_b', password='password123')
        resp_json = self.client.get(reverse('reports:daily_task_detail', args=[report_a.id]))
        self.assertEqual(resp_json.status_code, 403)

        # Log in as Employee A (task owner)
        self.client.login(username='emp_a', password='password123')
        resp_owner = self.client.get(reverse('reports:daily_task_detail', args=[report_a.id]))
        data_owner = resp_owner.json()
        self.assertTrue(data_owner['can_view_comments'])
        self.assertEqual(len(data_owner['comments']), 1)

    # 13. Employee dashboard privacy: Only own boss comments are rendered.
    def test_employee_dashboard_only_shows_own_boss_comments(self):
        report_a = DailyTaskReport.objects.create(
            employee=self.emp_a,
            report_date=date.today(),
            task_description="Emp A work"
        )
        report_b = DailyTaskReport.objects.create(
            employee=self.emp_b,
            report_date=date.today(),
            task_description="Emp B work"
        )

        DailyTaskComment.objects.create(
            daily_task_report=report_a,
            boss=self.boss,
            comment="Secret comment for Emp A"
        )
        DailyTaskComment.objects.create(
            daily_task_report=report_b,
            boss=self.boss,
            comment="Secret comment for Emp B"
        )

        # Employee A logs in -> Dashboard must ONLY contain Emp A's comment
        self.client.login(username='emp_a', password='password123')
        response_a = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response_a.status_code, 200)
        self.assertContains(response_a, "Secret comment for Emp A")
        self.assertNotContains(response_a, "Secret comment for Emp B")

        # Employee B logs in -> Dashboard must ONLY contain Emp B's comment
        self.client.login(username='emp_b', password='password123')
        response_b = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response_b.status_code, 200)
        self.assertContains(response_b, "Secret comment for Emp B")
        self.assertNotContains(response_b, "Secret comment for Emp A")

    # 13. Assigned tasks workflow: Boss assigns task with priority, Employee updates status.
    def test_assigned_tasks_workflow(self):
        from reports.models import AssignedTask
        self.client.login(username='bossuser', password='password123')

        # Boss assigns task to Employee A with HIGH priority
        response_assign = self.client.post(reverse('reports:task_create'), {
            'title': 'Audit Preparation',
            'description': 'Gather documents for audit',
            'assigned_to': self.emp_a.id,
            'priority': AssignedTask.HIGH
        })
        self.assertEqual(response_assign.status_code, 302)

        task = AssignedTask.objects.get(title='Audit Preparation')
        self.assertEqual(task.assigned_to, self.emp_a)
        self.assertEqual(task.priority, AssignedTask.HIGH)
        self.assertEqual(task.status, AssignedTask.PENDING)

        # Log in as Employee A and update status to COMPLETED
        self.client.login(username='emp_a', password='password123')
        response_status = self.client.post(reverse('reports:task_status_update', args=[task.id]), {
            'status': AssignedTask.COMPLETED
        })
        self.assertEqual(response_status.status_code, 302)

        task.refresh_from_db()
        self.assertEqual(task.status, AssignedTask.COMPLETED)

    # 14. Boss can reset employee password.
    def test_boss_can_reset_employee_password(self):
        # Non-boss employee attempt -> 403
        self.client.login(username='emp_a', password='password123')
        resp_forbidden = self.client.get(reverse('accounts:employee_reset_password_by_boss', args=[self.emp_b.id]))
        self.assertEqual(resp_forbidden.status_code, 403)

        # Boss login -> change Emp B password
        self.client.login(username='bossuser', password='password123')
        response = self.client.post(reverse('accounts:employee_reset_password_by_boss', args=[self.emp_b.id]), {
            'new_password': 'newpassword456',
            'confirm_password': 'newpassword456'
        })
        self.assertEqual(response.status_code, 302)

        # Verify Employee B can log in with new password
        self.client.logout()
        login_success = self.client.login(username='emp_b', password='newpassword456')
        self.assertTrue(login_success)

    # 15. Employee task submitted from dashboard updates Daily Report matrix
    def test_dashboard_task_submission_updates_daily_report_matrix(self):
        self.client.login(username='emp_a', password='password123')
        today_str = date.today().strftime('%Y-%m-%d')
        
        response = self.client.post(reverse('reports:daily_task_save'), {
            'report_date': today_str,
            'task_description': 'Completed feature X implementation on dashboard.'
        })
        self.assertEqual(response.status_code, 302)

        # Check DB entry exists
        report = DailyTaskReport.objects.filter(employee=self.emp_a, report_date=date.today()).first()
        self.assertIsNotNone(report)
        self.assertEqual(report.task_description, 'Completed feature X implementation on dashboard.')

        # Check Daily Report matrix page renders task description text
        daily_rep_res = self.client.get(reverse('reports:daily_report'))
        self.assertEqual(daily_rep_res.status_code, 200)
        self.assertContains(daily_rep_res, 'Completed feature X implementation on dashboard.')

    # 16. Render Keep-Alive Ping Endpoint Returns 200 OK
    def test_keep_alive_ping_endpoint(self):
        res = self.client.get(reverse('accounts:ping'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content.decode(), 'PONG')

        root_res = self.client.get(reverse('root_ping'))
        self.assertEqual(root_res.status_code, 200)
        self.assertEqual(root_res.content.decode(), 'PONG')




