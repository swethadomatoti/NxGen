from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from campaign.models import Campaign
from instructors.models import Instructor
from LeadManagement.models import Lead
from .models import DemoAttendance, DemoSchedule


class DemoScheduleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='password123',
            role=User.ADMIN,
        )
        self.client.force_authenticate(user=self.admin_user)

        self.campaign = Campaign.objects.create(
            name='Spring Campaign',
            status='active',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )

        instructor_user = User.objects.create_user(
            username='instructor',
            email='instructor@example.com',
            password='password123',
            role=User.INSTRUCTOR,
        )
        self.instructor = Instructor.objects.create(
            user=instructor_user,
            full_name='Demo Instructor',
            phone='9876543210',
            email='instructor@example.com',
            experience='Fresher',
        )

    @patch('Demo.views.send_demo_schedule_emails')
    def test_bulk_demo_schedule_creates_demo_and_assigns_interested_leads(self, mock_send_emails):
        Lead.objects.create(
            fullname='Interested Lead',
            email='lead1@example.com',
            phone_number='1234567890',
            status='interested',
            campaign=self.campaign,
        )
        Lead.objects.create(
            fullname='Contacted Lead',
            email='lead2@example.com',
            phone_number='0987654321',
            status='contacted',
            campaign=self.campaign,
        )

        payload = {
            'campaign_id': self.campaign.id,
            'instructor_id': self.instructor.id,
            'date': date.today().isoformat(),
            'time': '14:30',
            'meeting_link': 'https://example.com/demo',
        }

        response = self.client.post('/api/demo/schedule/', data=payload, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['message'], 'Demo scheduled successfully')
        self.assertEqual(response.data['total_leads'], 1)
        self.assertEqual(response.data['demo_schedule']['campaign'], 'Spring Campaign')
        self.assertEqual(response.data['demo_schedule']['instructor'], 'Demo Instructor')
        self.assertEqual(response.data['demo_schedule']['link'], 'https://example.com/demo')
        self.assertIsInstance(response.data['demo_schedule']['scheduled_at'], str)

        demo_schedule = DemoSchedule.objects.get(campaign=self.campaign, instructor=self.instructor)
        self.assertEqual(demo_schedule.leads.count(), 1)
        self.assertTrue(demo_schedule.leads.filter(status='interested').exists())
        mock_send_emails.assert_called_once_with(demo_schedule.id)

    @patch('Demo.views.send_demo_schedule_emails', side_effect=Exception('SMTP failure'))
    def test_bulk_demo_schedule_continues_when_email_send_fails(self, mock_send_emails):
        Lead.objects.create(
            fullname='Interested Lead',
            email='lead1@example.com',
            phone_number='1234567890',
            status='interested',
            campaign=self.campaign,
        )

        payload = {
            'campaign_id': self.campaign.id,
            'instructor_id': self.instructor.id,
            'date': date.today().isoformat(),
            'time': '14:30',
            'meeting_link': 'https://example.com/demo',
        }

        response = self.client.post('/api/demo/schedule/', data=payload, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['message'], 'Demo scheduled successfully')
        self.assertTrue(DemoSchedule.objects.filter(campaign=self.campaign, instructor=self.instructor).exists())

    def test_bulk_demo_schedule_returns_no_interested_leads(self):
        Lead.objects.create(
            fullname='Contacted Lead',
            email='lead2@example.com',
            phone_number='0987654321',
            status='contacted',
            campaign=self.campaign,
        )

        payload = {
            'campaign_id': self.campaign.id,
            'instructor_id': self.instructor.id,
            'date': date.today().isoformat(),
            'time': '14:30',
            'meeting_link': 'https://example.com/demo',
        }

        response = self.client.post('/api/demo/schedule/', data=payload, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], 'No interested leads found')
        self.assertFalse(DemoSchedule.objects.filter(campaign=self.campaign, instructor=self.instructor).exists())

    @patch('Demo.views.send_demo_schedule_emails')
    def test_bulk_demo_schedule_with_frontend_field_names(self, mock_send_emails):
        Lead.objects.create(
            fullname='Interested Lead',
            email='lead1@example.com',
            phone_number='1234567890',
            status='interested',
            campaign=self.campaign,
        )

        payload = {
            'campaign': 'Spring Campaign',
            'date': date.today().isoformat(),
            'instructor': 'Demo Instructor',
            'link': 'https://teams.live.com/meet/9325079070210',
            'time': '10:30',
        }

        response = self.client.post('/api/demo/schedule/', data=payload, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['message'], 'Demo scheduled successfully')
        self.assertEqual(response.data['total_leads'], 1)

        demo_schedule = DemoSchedule.objects.get(campaign=self.campaign, instructor=self.instructor)
        self.assertEqual(demo_schedule.leads.count(), 1)
        mock_send_emails.assert_called_once_with(demo_schedule.id)

    def test_demo_schedule_list_view(self):
        demo_schedule = DemoSchedule.objects.create(
            campaign=self.campaign,
            instructor=self.instructor,
            scheduled_at=timezone.now(),
            meeting_link='https://example.com/demo',
            created_by=self.admin_user,
        )
        demo_lead = Lead.objects.create(
            fullname='Test Lead',
            email='test@example.com',
            phone_number='1234567890',
            status='interested',
            campaign=self.campaign,
        )
        demo_schedule.leads.add(demo_lead)

        response = self.client.get('/api/demo/', format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['campaign'], 'Spring Campaign')
        self.assertEqual(response.data[0]['instructor'], 'Demo Instructor')
        self.assertEqual(response.data[0]['total_leads'], 1)

    def test_demo_schedule_attendance_cannot_be_marked_before_demo_time(self):
        demo_schedule = DemoSchedule.objects.create(
            campaign=self.campaign,
            instructor=self.instructor,
            scheduled_at=timezone.now() + timedelta(hours=1),
            meeting_link='https://example.com/demo',
            created_by=self.admin_user,
        )
        demo_lead = Lead.objects.create(
            fullname='Test Lead',
            email='test@example.com',
            phone_number='1234567890',
            status='interested',
            campaign=self.campaign,
        )
        demo_schedule.leads.add(demo_lead)

        payload = {
            'attendance': [
                {'id': demo_lead.id, 'attended': True},
            ]
        }

        response = self.client.post(
            f'/api/demo/{demo_schedule.id}/attendance/',
            data=payload,
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['error'],
            'Attendance can only be marked after the scheduled demo time.',
        )

    def test_demo_schedule_attendance_marked_after_demo_time(self):
        demo_schedule = DemoSchedule.objects.create(
            campaign=self.campaign,
            instructor=self.instructor,
            scheduled_at=timezone.now() - timedelta(hours=1),
            meeting_link='https://example.com/demo',
            created_by=self.admin_user,
        )
        demo_lead = Lead.objects.create(
            fullname='Test Lead',
            email='test@example.com',
            phone_number='1234567890',
            status='interested',
            campaign=self.campaign,
        )
        demo_schedule.leads.add(demo_lead)

        payload = {
            'attendance': [
                {'id': demo_lead.id, 'attended': True},
            ]
        }

        response = self.client.post(
            f'/api/demo/{demo_schedule.id}/attendance/',
            data=payload,
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        updated_entry = DemoAttendance.objects.get(demo_schedule=demo_schedule, lead=demo_lead)
        self.assertTrue(updated_entry.attended)
        self.assertIsNotNone(updated_entry.attended_at)
        self.assertEqual(response.data['status'], DemoSchedule.STATUS_ATTENDED)
        self.assertEqual(response.data['attended_count'], 1)
        self.assertEqual(response.data['total_leads'], 1)
        if 'leads' in response.data:
            self.assertEqual(response.data['leads'][0]['id'], demo_lead.id)
            self.assertTrue(response.data['leads'][0]['attended'])
        else:
            self.assertIsNotNone(response.data)

    def test_demo_schedule_status_becomes_completed_after_all_leads_attend_for_rescheduled_demo(self):
        demo_schedule = DemoSchedule.objects.create(
            campaign=self.campaign,
            instructor=self.instructor,
            scheduled_at=timezone.now() - timedelta(hours=1),
            meeting_link='https://example.com/demo',
            created_by=self.admin_user,
        )
        demo_lead_1 = Lead.objects.create(
            fullname='Lead One',
            email='lead1@example.com',
            phone_number='1234567890',
            status='interested',
            campaign=self.campaign,
        )
        demo_lead_2 = Lead.objects.create(
            fullname='Lead Two',
            email='lead2@example.com',
            phone_number='0987654321',
            status='interested',
            campaign=self.campaign,
        )
        demo_schedule.leads.add(demo_lead_1, demo_lead_2)

        # mark first demo attendance as not attended and reschedule
        payload = {'attendance': [{'id': demo_lead_1.id, 'attended': False}, {'id': demo_lead_2.id, 'attended': False}]}
        self.client.post(f'/api/demo/{demo_schedule.id}/attendance/', data=payload, format='json')

        scheduled_datetime = timezone.now() - timedelta(hours=1)
        response = self.client.post(
            f'/api/demo/{demo_schedule.id}/reschedule/',
            data={
                'instructor_id': self.instructor.id,
                'date': scheduled_datetime.date().isoformat(),
                'time': scheduled_datetime.time().strftime('%H:%M:%S'),
                'meeting_link': 'https://example.com/rescheduled-demo',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        demo_schedule.refresh_from_db()
        self.assertEqual(demo_schedule.status, DemoSchedule.STATUS_RESCHEDULED)
        self.assertEqual(DemoSchedule.objects.filter(pk=demo_schedule.id).count(), 1)
        # Compare date and time separately, ignoring microseconds
        self.assertEqual(demo_schedule.scheduled_at.date(), scheduled_datetime.date())
        db_time = demo_schedule.scheduled_at.replace(microsecond=0)
        expected_time = scheduled_datetime.replace(microsecond=0)
        self.assertEqual(db_time, expected_time)

        payload = {'attendance': [{'id': demo_lead_1.id, 'attended': True}, {'id': demo_lead_2.id, 'attended': True}]}
        response = self.client.post(
            f'/api/demo/{demo_schedule.id}/attendance/',
            data={
                'attendance': [
                    {'id': demo_lead_1.id, 'attended': True},
                    {'id': demo_lead_2.id, 'attended': True},
                ]
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        demo_schedule.refresh_from_db()
        self.assertEqual(demo_schedule.status, DemoSchedule.STATUS_COMPLETED)

    def test_demo_schedule_reschedules_original_demo_status(self):
        demo_schedule = DemoSchedule.objects.create(
            campaign=self.campaign,
            instructor=self.instructor,
            scheduled_at=timezone.now() - timedelta(hours=1),
            meeting_link='https://example.com/demo',
            created_by=self.admin_user,
        )
        demo_lead = Lead.objects.create(
            fullname='Test Lead',
            email='test@example.com',
            phone_number='1234567890',
            status='interested',
            campaign=self.campaign,
        )
        demo_schedule.leads.add(demo_lead)

        response = self.client.post(
            f'/api/demo/{demo_schedule.id}/reschedule/',
            data={
                'instructor_id': self.instructor.id,
                'date': date.today().isoformat(),
                'time': '13:00',
                'meeting_link': 'https://example.com/rescheduled-demo',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        demo_schedule.refresh_from_db()
        self.assertEqual(demo_schedule.status, DemoSchedule.STATUS_RESCHEDULED)

    def test_rescheduled_demo_attendance_allows_parent_chain_leads(self):
        demo_schedule = DemoSchedule.objects.create(
            campaign=self.campaign,
            instructor=self.instructor,
            scheduled_at=timezone.now() - timedelta(hours=1),
            meeting_link='https://example.com/demo',
            created_by=self.admin_user,
        )
        lead_one = Lead.objects.create(
            fullname='Lead One',
            email='lead1@example.com',
            phone_number='1234567890',
            status='interested',
            campaign=self.campaign,
        )
        lead_two = Lead.objects.create(
            fullname='Lead Two',
            email='lead2@example.com',
            phone_number='0987654321',
            status='interested',
            campaign=self.campaign,
        )
        demo_schedule.leads.add(lead_one, lead_two)

        # Mark lead_one as attended and leave lead_two not attended.
        self.client.post(
            f'/api/demo/{demo_schedule.id}/attendance/',
            data={
                'attendance': [
                    {'id': lead_one.id, 'attended': True},
                    {'id': lead_two.id, 'attended': False},
                ]
            },
            format='json',
        )

        response = self.client.post(
            f'/api/demo/{demo_schedule.id}/reschedule/',
            data={
                'instructor_id': self.instructor.id,
                'date': date.today().isoformat(),
                'time': '13:00',
                'meeting_link': 'https://example.com/rescheduled-demo',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)

        demo_schedule.refresh_from_db()
        self.assertEqual(demo_schedule.leads.count(), 2)
        all_leads_in_chain = set(demo_schedule.get_all_leads().values_list('id', flat=True))
        self.assertEqual(all_leads_in_chain, {lead_one.id, lead_two.id})

        # Update the demo's scheduled time to past so we can mark attendance
        demo_schedule.scheduled_at = timezone.now() - timedelta(hours=1)
        demo_schedule.save()

        payload = {
            'attendance': [
                {'id': lead_one.id, 'attended': True},
                {'id': lead_two.id, 'attended': True},
            ]
        }
        response = self.client.post(
            f'/api/demo/{demo_schedule.id}/attendance/',
            data=payload,
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        demo_schedule.refresh_from_db()
        self.assertEqual(demo_schedule.status, DemoSchedule.STATUS_COMPLETED)

    def test_rescheduled_demo_leads_include_all_related_leads(self):
        demo_schedule = DemoSchedule.objects.create(
            campaign=self.campaign,
            instructor=self.instructor,
            scheduled_at=timezone.now() - timedelta(hours=1),
            meeting_link='https://example.com/demo',
            created_by=self.admin_user,
        )
        lead_one = Lead.objects.create(
            fullname='Lead One',
            email='lead1@example.com',
            phone_number='1234567890',
            status='interested',
            campaign=self.campaign,
        )
        lead_two = Lead.objects.create(
            fullname='Lead Two',
            email='lead2@example.com',
            phone_number='0987654321',
            status='interested',
            campaign=self.campaign,
        )
        demo_schedule.leads.add(lead_one, lead_two)

        payload = {
            'attendance': [
                {'id': lead_one.id, 'attended': False},
                {'id': lead_two.id, 'attended': False},
            ]
        }
        self.client.post(f'/api/demo/{demo_schedule.id}/attendance/', data=payload, format='json')

        response = self.client.post(
            f'/api/demo/{demo_schedule.id}/reschedule/',
            data={
                'instructor_id': self.instructor.id,
                'date': date.today().isoformat(),
                'time': '13:00',
                'meeting_link': 'https://example.com/rescheduled-demo',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)

        demo_schedule.refresh_from_db()
        self.assertEqual(DemoSchedule.objects.filter(pk=demo_schedule.id).count(), 1)

        response = self.client.get(f'/api/demo/{demo_schedule.id}/leads/', format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({lead['id'] for lead in response.data}, {lead_one.id, lead_two.id})
        self.assertTrue(all(lead['attended'] is False for lead in response.data))

    def test_demo_schedule_detail_view_get(self):
        demo_schedule = DemoSchedule.objects.create(
            campaign=self.campaign,
            instructor=self.instructor,
            scheduled_at=timezone.now(),
            meeting_link='https://example.com/demo',
            created_by=self.admin_user,
        )

        response = self.client.get(f'/api/demo/{demo_schedule.id}/', format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['campaign'], 'Spring Campaign')
        self.assertEqual(response.data['instructor'], 'Demo Instructor')

    def test_demo_schedule_detail_view_put(self):
        demo_schedule = DemoSchedule.objects.create(
            campaign=self.campaign,
            instructor=self.instructor,
            scheduled_at=timezone.now(),
            meeting_link='https://example.com/demo',
            created_by=self.admin_user,
        )

        new_scheduled_at = timezone.now() + timedelta(hours=1)
        payload = {
            'scheduled_at': new_scheduled_at.isoformat(),
            'meeting_link': 'https://example.com/updated-demo',
        }

        response = self.client.put(f'/api/demo/{demo_schedule.id}/', data=payload, format='json')

        self.assertEqual(response.status_code, 200)
        demo_schedule.refresh_from_db()
        self.assertEqual(demo_schedule.meeting_link, 'https://example.com/updated-demo')

    def test_demo_schedule_detail_view_delete(self):
        demo_schedule = DemoSchedule.objects.create(
            campaign=self.campaign,
            instructor=self.instructor,
            scheduled_at=timezone.now(),
            meeting_link='https://example.com/demo',
            created_by=self.admin_user,
        )

        response = self.client.delete(f'/api/demo/{demo_schedule.id}/', format='json')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(DemoSchedule.objects.filter(pk=demo_schedule.id).exists())

    def test_demo_schedule_detail_view_not_found(self):
        response = self.client.get('/api/demo/999/', format='json')
        self.assertEqual(response.status_code, 404)

        response = self.client.put('/api/demo/999/', data={}, format='json')
        self.assertEqual(response.status_code, 404)

        response = self.client.delete('/api/demo/999/', format='json')
        self.assertEqual(response.status_code, 404)
