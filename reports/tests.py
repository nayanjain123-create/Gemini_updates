from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from reports.models import AssignedTask, TaskReallocation, TaskRemark, Notification, DailyTaskReport

class TaskWorkflowTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_user(
            username='boss_user',
            email='boss@test.com',
            full_name='Boss Manager',
            role=User.BOSS,
            password='password123'
        )
        self.rupali = User.objects.create_user(
            username='rupali',
            email='rupali@test.com',
            full_name='Rupali S',
            role=User.EMPLOYEE,
            password='password123'
        )
        self.rachana = User.objects.create_user(
            username='rachana',
            email='rachana@test.com',
            full_name='Rachana P',
            role=User.EMPLOYEE,
            password='password123'
        )
        self.client = Client()

    def test_complete_task_workflow(self):
        # 1. Boss allocates task to Rupali
        self.client.login(username='boss_user', password='password123')
        create_resp = self.client.post(reverse('reports:task_create'), {
            'title': 'Complete the returns for container 4',
            'description': 'Process paperwork for container 4',
            'assigned_to': self.rupali.id,
            'priority': 'URGENT',
        })
        self.assertEqual(create_resp.status_code, 302)

        task = AssignedTask.objects.get(title='Complete the returns for container 4')
        self.assertEqual(task.assigned_to, self.rupali)
        self.assertEqual(task.original_assigned_to, self.rupali)
        self.assertEqual(task.status, AssignedTask.PENDING)

        # Verify Rupali received notification
        notif_rupali = Notification.objects.filter(recipient=self.rupali).first()
        self.assertIsNotNone(notif_rupali)
        self.assertEqual(notif_rupali.notification_type, Notification.TASK_ASSIGNED)

        # 2. Rupali delegates/re-allocates task to Rachana with reason
        self.client.login(username='rupali', password='password123')
        realloc_resp = self.client.post(reverse('reports:task_reallocate', args=[task.id]), {
            'reallocate_to': self.rachana.id,
            'reason': 'Occupied with emergency dispatch, Rachana handling container 4'
        })
        self.assertEqual(realloc_resp.status_code, 302)

        task.refresh_from_db()
        self.assertEqual(task.assigned_to, self.rachana)
        self.assertTrue(task.is_reallocated)
        self.assertEqual(task.reallocation_reason, 'Occupied with emergency dispatch, Rachana handling container 4')

        # Check TaskReallocation history
        realloc_rec = TaskReallocation.objects.filter(task=task).first()
        self.assertIsNotNone(realloc_rec)
        self.assertEqual(realloc_rec.reallocated_by, self.rupali)
        self.assertEqual(realloc_rec.reallocated_to, self.rachana)

        # Verify Boss and Rachana both received notifications
        boss_realloc_notif = Notification.objects.filter(recipient=self.boss, notification_type=Notification.TASK_REALLOCATED).first()
        self.assertIsNotNone(boss_realloc_notif)
        self.assertIn('Rachana', boss_realloc_notif.message)

        rachana_realloc_notif = Notification.objects.filter(recipient=self.rachana, notification_type=Notification.TASK_REALLOCATED).first()
        self.assertIsNotNone(rachana_realloc_notif)
        self.assertIn('Rupali', rachana_realloc_notif.message)

        # 3. Rachana marks task as completed -> Status becomes WAITING_APPROVAL, boss notified
        self.client.login(username='rachana', password='password123')
        complete_resp = self.client.post(reverse('reports:task_mark_complete', args=[task.id]))
        self.assertEqual(complete_resp.status_code, 302)

        task.refresh_from_db()
        self.assertEqual(task.status, AssignedTask.WAITING_APPROVAL)

        boss_comp_notif = Notification.objects.filter(recipient=self.boss, notification_type=Notification.TASK_COMPLETED_WAITING_APPROVAL).first()
        self.assertIsNotNone(boss_comp_notif)
        self.assertIn('waiting for your approval', boss_comp_notif.message.lower())

        # 4. Boss adds Remark -> Status switches back to PENDING, Rachana notified
        self.client.login(username='boss_user', password='password123')
        remark_resp = self.client.post(reverse('reports:task_remark', args=[task.id]), {
            'remark': 'Missing custom clearance certificate copy. Please attach.'
        })
        self.assertEqual(remark_resp.status_code, 302)

        task.refresh_from_db()
        self.assertEqual(task.status, AssignedTask.PENDING)
        self.assertEqual(task.boss_remark, 'Missing custom clearance certificate copy. Please attach.')

        remark_rec = TaskRemark.objects.filter(task=task).first()
        self.assertIsNotNone(remark_rec)
        self.assertEqual(remark_rec.remark, 'Missing custom clearance certificate copy. Please attach.')

        rachana_rmk_notif = Notification.objects.filter(recipient=self.rachana, notification_type=Notification.TASK_REVISION_REQUESTED).first()
        self.assertIsNotNone(rachana_rmk_notif)

        # 5. Rachana fixes and marks completed again
        self.client.login(username='rachana', password='password123')
        self.client.post(reverse('reports:task_mark_complete', args=[task.id]))
        task.refresh_from_db()
        self.assertEqual(task.status, AssignedTask.WAITING_APPROVAL)

        # 6. Boss approves task
        self.client.login(username='boss_user', password='password123')
        approve_resp = self.client.post(reverse('reports:task_approve', args=[task.id]))
        self.assertEqual(approve_resp.status_code, 302)

        task.refresh_from_db()
        self.assertEqual(task.status, AssignedTask.APPROVED)
        self.assertIsNotNone(task.approved_at)

        rachana_appr_notif = Notification.objects.filter(recipient=self.rachana, notification_type=Notification.TASK_APPROVED).first()
        self.assertIsNotNone(rachana_appr_notif)

    def test_dashboard_renders(self):
        # Test Boss dashboard view
        self.client.login(username='boss_user', password='password123')
        resp_boss = self.client.get(reverse('dashboard:index'))
        self.assertEqual(resp_boss.status_code, 200)
        self.assertContains(resp_boss, 'Employee Workload & Performance Scoreboard')

        # Test Employee dashboard view
        self.client.login(username='rupali', password='password123')
        resp_emp = self.client.get(reverse('dashboard:index'))
        self.assertEqual(resp_emp.status_code, 200)
        self.assertContains(resp_emp, "Today's Daily Report")
