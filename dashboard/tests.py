from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from reports.models import DailyTaskReport, AssignedTask
from compliance.models import ComplianceItem

class CommandPaletteTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.boss = User.objects.create_user(
            username='bossman',
            email='bossman@gemini.com',
            password='password123',
            full_name='Chief Executive',
            role=User.BOSS,
            is_staff=True
        )
        self.emp = User.objects.create_user(
            username='johndoe',
            email='john@gemini.com',
            password='password123',
            full_name='John Doe',
            role=User.EMPLOYEE
        )

        today = timezone.now().date()
        self.daily_report = DailyTaskReport.objects.create(
            employee=self.emp,
            report_date=today,
            task_description='Built new feature and tested accounting integration',
            status=DailyTaskReport.COMPLETED,
            priority=DailyTaskReport.HIGH
        )

        self.assigned_task = AssignedTask.objects.create(
            title='Prepare Q3 Tax Documents',
            description='Audit all receipts for LLP',
            assigned_by=self.boss,
            assigned_to=self.emp,
            status=AssignedTask.WAITING_APPROVAL,
            priority=AssignedTask.URGENT
        )

        # Create compliance item
        compliance_year = today.year - 1 if today.month == 1 else today.year
        compliance_month = 12 if today.month == 1 else today.month - 1
        self.comp_item = ComplianceItem.objects.create(
            company=ComplianceItem.LLP,
            compliance_type=ComplianceItem.GSTR_3B,
            month=compliance_month,
            year=compliance_year,
            status=ComplianceItem.DONE,
            completed_by=self.emp,
            completed_at=timezone.now(),
            reference_number='CHAL-998877',
            remarks='Filed on time'
        )

    def test_anonymous_user_redirected(self):
        url = reverse('dashboard:command_palette_api')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_employee_user_forbidden(self):
        self.client.login(username='johndoe', password='password123')
        url = reverse('dashboard:command_palette_api')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn('Forbidden', data.get('error', ''))

    def test_boss_user_empty_query(self):
        self.client.login(username='bossman', password='password123')
        url = reverse('dashboard:command_palette_api')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('mode'), 'default')
        self.assertIn('stats', data)
        self.assertIn('quick_suggestions', data)

    def test_boss_search_employee_name(self):
        self.client.login(username='bossman', password='password123')
        url = reverse('dashboard:command_palette_api') + '?q=john'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('mode'), 'search')
        self.assertTrue(len(data.get('employees', [])) > 0)

        emp_result = data['employees'][0]
        self.assertEqual(emp_result['username'], 'johndoe')
        # Check today's report details
        self.assertTrue(emp_result['today_report']['submitted'])
        self.assertEqual(emp_result['today_report']['status'], DailyTaskReport.COMPLETED)
        # Check completed compliances
        self.assertTrue(len(emp_result['compliances_completed']) > 0)
        self.assertEqual(emp_result['compliances_completed'][0]['reference_number'], 'CHAL-998877')
        # Check assigned tasks
        self.assertTrue(len(emp_result['tasks']) > 0)
        self.assertEqual(emp_result['tasks'][0]['title'], 'Prepare Q3 Tax Documents')

    def test_boss_search_company_name(self):
        self.client.login(username='bossman', password='password123')
        url = reverse('dashboard:command_palette_api') + '?q=llp'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data.get('company'))
        self.assertEqual(data['company']['code'], 'LLP')
        self.assertTrue(data['company']['completed_count'] >= 1)
        self.assertEqual(data['company']['completed'][0]['completed_by'], 'John Doe')

    def test_boss_search_report_keyword(self):
        self.client.login(username='bossman', password='password123')
        url = reverse('dashboard:command_palette_api') + '?q=report'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data.get('report'))
        self.assertEqual(data['report']['submitted_count'], 1)
        self.assertEqual(data['report']['submitted'][0]['name'], 'John Doe')

    def test_boss_search_compliance_keyword(self):
        self.client.login(username='bossman', password='password123')
        url = reverse('dashboard:command_palette_api') + '?q=compliance'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data.get('compliance'))
        self.assertTrue(len(data['compliance']['companies']) > 0)

    def test_employee_dashboard_shows_statutory_countdown(self):
        from unittest.mock import patch
        from datetime import datetime
        # GSTR-1 is due on the 11th of the month. Mock date to 10th to test the 48h active countdown window.
        mock_now = timezone.make_aware(datetime(2026, 9, 10, 10, 0))
        with patch('django.utils.timezone.now', return_value=mock_now):
            self.client.login(username='johndoe', password='password123')
            response = self.client.get(reverse('dashboard:index'))
            self.assertEqual(response.status_code, 200)
            # Check that other_employees exists in context
            self.assertIn('other_employees', response.context)
            # Check that urgent_statutory_deadlines exists in context
            self.assertIn('urgent_statutory_deadlines', response.context)
            # Check template rendered beside-welcome card with countdown
            self.assertContains(response, 'tax-countdown-card')
            self.assertContains(response, 'GSTR-1')
            self.assertContains(response, 'GI, GTW, HUF, International, LLP')

    def test_boss_dashboard_does_not_show_employee_statutory_countdown(self):
        self.client.login(username='bossman', password='password123')
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        # Boss dashboard should NOT display employee countdown card
        self.assertNotContains(response, 'tax-countdown-card')

