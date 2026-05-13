import logging
from datetime import datetime, timezone as dt_timezone

import pytz
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from campaign.models import Campaign
from instructors.models import Instructor
from LeadManagement.models import Lead

from .models import DemoSchedule, DemoAttendance
from .serializers import (
    DemoScheduleCreateSerializer,
    DemoScheduleSerializer,
    DemoScheduleUpdateSerializer,
    DemoScheduleAttendanceSerializer,
    DemoScheduleLeadSerializer,
    RescheduleDemoSerializer,
)
from .tasks import send_demo_schedule_emails, send_demo_reschedule_emails

logger = logging.getLogger(__name__)


class BulkDemoScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DemoScheduleCreateSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("Demo scheduling validation failed: %s", serializer.errors)
            return Response(
                {"error": "Invalid request data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        campaign_id = serializer.validated_data['campaign_id']
        instructor_id = serializer.validated_data['instructor_id']
        scheduled_date = serializer.validated_data['date']
        scheduled_time = serializer.validated_data['time']
        meeting_link = serializer.validated_data['meeting_link']

        campaign = Campaign.objects.filter(pk=campaign_id).first()
        if campaign is None:
            return Response({"error": "Campaign not found."}, status=status.HTTP_404_NOT_FOUND)

        instructor = Instructor.objects.filter(pk=instructor_id).first()
        if instructor is None:
            return Response({"error": "Instructor not found."}, status=status.HTTP_404_NOT_FOUND)

        interested_leads = Lead.objects.filter(campaign=campaign, status='interested')
        total_leads = interested_leads.count()
        if total_leads == 0:
            logger.info(
                "No interested leads found for campaign %s while scheduling demo", campaign_id,
            )
            return Response({"message": "No interested leads found"}, status=status.HTTP_200_OK)

        # Store as naive datetime in IST (USE_TZ=False)
        scheduled_at = datetime.combine(scheduled_date, scheduled_time)

        try:
            with transaction.atomic():
                demo_schedule = DemoSchedule.objects.create(
                    campaign=campaign,
                    instructor=instructor,
                    scheduled_at=scheduled_at,
                    meeting_link=meeting_link,
                    created_by=request.user,
                )
                demo_schedule.leads.add(*interested_leads)
                logger.info(
                    "Demo scheduled: id=%s campaign=%s instructor=%s leads=%s created_by=%s",
                    demo_schedule.id,
                    campaign.id,
                    instructor.id,
                    total_leads,
                    request.user.id,
                )
        except Exception as exc:
            logger.exception(
                "Failed to create demo schedule for campaign %s instructor %s: %s",
                campaign_id,
                instructor_id,
                exc,
            )
            return Response(
                {"error": "Failed to schedule demo"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            send_demo_schedule_emails(demo_schedule.id)
        except Exception as exc:
            logger.exception(
                "Failed to send demo emails synchronously for Demo schedule %s: %s",
                demo_schedule.id,
                exc,
            )

        response_serializer = DemoScheduleSerializer(demo_schedule, context={'request': request})
        return Response(
            {
                "message": "Demo scheduled successfully",
                "total_leads": total_leads,
                "demo_schedule": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class DemoScheduleListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        demo_schedules = DemoSchedule.objects.select_related(
            'campaign', 'instructor', 'created_by'
        ).prefetch_related('leads', 'demo_attendances')

        serializer = DemoScheduleSerializer(demo_schedules, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class DemoScheduleAttendanceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            demo_schedule = DemoSchedule.objects.select_related(
                'campaign', 'instructor', 'created_by'
            ).prefetch_related('leads', 'demo_attendances').get(pk=pk)
        except DemoSchedule.DoesNotExist:
            return Response({"error": "Demo schedule not found"}, status=status.HTTP_404_NOT_FOUND)

        scheduled_at = demo_schedule.scheduled_at

        current_time = timezone.now()
        if timezone.is_aware(current_time):
            current_time = timezone.make_naive(current_time)

        if timezone.is_aware(scheduled_at):
            scheduled_at = timezone.make_naive(scheduled_at)

        if current_time < scheduled_at:
            return Response(
                {"error": "Attendance can only be marked after the scheduled demo time."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DemoScheduleAttendanceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid attendance data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_lead_ids = set(demo_schedule.get_all_leads().values_list('id', flat=True))
        for item in serializer.validated_data['attendance']:
            if item['id'] not in valid_lead_ids:
                return Response(
                    {"error": f"Lead {item['id']} is not part of this demo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            DemoAttendance.objects.update_or_create(
                demo_schedule=demo_schedule,
                lead_id=item['id'],
                defaults={
                    'attended': item['attended'],
                    'attended_at': timezone.now() if item['attended'] else None,
                },
            )

        demo_schedule.update_status_after_attendance()
        demo_schedule = DemoSchedule.objects.select_related(
            'campaign', 'instructor', 'created_by'
        ).prefetch_related('leads', 'demo_attendances').get(pk=pk)

        response_serializer = DemoScheduleSerializer(demo_schedule, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class DemoScheduleLeadsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            demo_schedule = DemoSchedule.objects.select_related(
                'campaign', 'instructor', 'created_by'
            ).prefetch_related('leads', 'demo_attendances').get(pk=pk)
        except DemoSchedule.DoesNotExist:
            return Response({"error": "Demo schedule not found"}, status=status.HTTP_404_NOT_FOUND)

        attendance_map = demo_schedule.get_aggregated_attendance()

        attendance_url = request.build_absolute_uri(
            reverse('demo_schedule_attendance', kwargs={'pk': demo_schedule.id})
        )

        lead_data = []
        for lead in demo_schedule.get_all_leads():
            attendance = attendance_map.get(lead.id)
            attended = False
            attended_at = None
            if attendance is not None:
                attended = attendance.attended
                if attendance.attended_at is not None:
                    attended_at = attendance.attended_at.strftime('%Y-%m-%d %H:%M:%S')

            lead_data.append({
                'id': lead.id,
                'fullname': lead.fullname,
                'email': lead.email,
                'attended': attended,
                'attended_at': attended_at,
                'attendance_url': attendance_url,
            })

        serializer = DemoScheduleLeadSerializer(lead_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DemoScheduleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_demo_schedule(self, pk):
        try:
            return DemoSchedule.objects.select_related(
                'campaign', 'instructor', 'created_by'
            ).prefetch_related('leads', 'demo_attendances').get(pk=pk)
        except DemoSchedule.DoesNotExist:
            return None

    def get(self, request, pk):
        demo_schedule = self.get_demo_schedule(pk)
        if demo_schedule is None:
            return Response({"error": "Demo schedule not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = DemoScheduleSerializer(demo_schedule, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        demo_schedule = self.get_demo_schedule(pk)
        if demo_schedule is None:
            return Response({"error": "Demo schedule not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = DemoScheduleUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid request data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scheduled_at = serializer.validated_data['scheduled_at']
        demo_schedule.scheduled_at = scheduled_at
        demo_schedule.meeting_link = serializer.validated_data['meeting_link']
        demo_schedule.save()

        logger.info(
            "Demo schedule updated: id=%s by user=%s",
            demo_schedule.id,
            request.user.id,
        )

        response_serializer = DemoScheduleSerializer(demo_schedule, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        demo_schedule = self.get_demo_schedule(pk)
        if demo_schedule is None:
            return Response({"error": "Demo schedule not found"}, status=status.HTTP_404_NOT_FOUND)

        demo_schedule.delete()

        logger.info(
            "Demo schedule deleted: id=%s by user=%s",
            pk,
            request.user.id,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class RescheduleDemoView(APIView):
    """
    Reschedule an existing demo schedule in place.
    Updates the existing demo record instead of creating a new one.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """
        Return reschedule preview data for the requested demo.
        Includes existing demo details and eligible non-attended interested leads.
        """
        try:
            original_demo = DemoSchedule.objects.select_related(
                'campaign', 'instructor', 'created_by'
            ).prefetch_related('leads', 'demo_attendances').get(pk=pk)
        except DemoSchedule.DoesNotExist:
            return Response(
                {"error": "Demo schedule not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        eligible_leads = []
        attendance_map = {
            attendance.lead_id: attendance
            for attendance in original_demo.demo_attendances.all()
        }

        for lead in original_demo.leads.all():
            attendance = attendance_map.get(lead.id)
            if (not attendance or not attendance.attended) and lead.status == 'interested':
                eligible_leads.append({
                    'id': lead.id,
                    'fullname': lead.fullname,
                    'email': lead.email,
                })

        scheduled_time = original_demo.scheduled_at
        formatted_scheduled_at = scheduled_time.strftime('%Y-%m-%d %H:%M:%S')

        return Response(
            {
                'demo_id': original_demo.id,
                'campaign': original_demo.campaign.name,
                'instructor': original_demo.instructor.full_name,
                'scheduled_at': formatted_scheduled_at,
                'meeting_link': original_demo.meeting_link,
                'status': original_demo.status,
                'eligible_leads_count': len(eligible_leads),
                'eligible_leads': eligible_leads,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, pk):
        """
        Reschedule the existing demo in place for non-attended interested leads.

        Request body:
        {
            "instructor_id": 1 (or "instructor": "John Doe"),
            "date": "2025-05-20",
            "time": "14:30:00",
            "meeting_link": "https://zoom.us/..."
        }
        """
        # Get the original demo schedule
        try:
            original_demo = DemoSchedule.objects.select_related(
                'campaign', 'instructor', 'created_by'
            ).prefetch_related('leads', 'demo_attendances').get(pk=pk)
        except DemoSchedule.DoesNotExist:
            return Response(
                {"error": "Demo schedule not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate request data
        serializer = RescheduleDemoSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("Demo reschedule validation failed: %s", serializer.errors)
            return Response(
                {"error": "Invalid request data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instructor_id = serializer.validated_data['instructor_id']
        scheduled_date = serializer.validated_data['date']
        scheduled_time = serializer.validated_data['time']
        meeting_link = serializer.validated_data['meeting_link']

        # Get instructor
        instructor = Instructor.objects.filter(pk=instructor_id).first()
        if instructor is None:
            return Response(
                {"error": "Instructor not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get leads who didn't attend but are interested
        non_attended_leads = []
        for lead in original_demo.leads.all():
            # Check if lead attended
            attendance = original_demo.demo_attendances.filter(lead=lead).first()
            
            # Include lead if didn't attend AND is interested
            if (not attendance or not attendance.attended) and lead.status == 'interested':
                non_attended_leads.append(lead)

        total_leads = len(non_attended_leads)
        if total_leads == 0:
            logger.info(
                "No non-attended interested leads found for demo %s to reschedule",
                pk
            )
            return Response(
                {"message": "No non-attended interested leads found for rescheduling"},
                status=status.HTTP_200_OK
            )

        # Update the existing demo schedule instead of creating a new record
        scheduled_at = datetime.combine(scheduled_date, scheduled_time)
        original_demo_data = {
            'scheduled_at': original_demo.scheduled_at,
            'meeting_link': original_demo.meeting_link,
        }

        try:
            with transaction.atomic():
                original_demo.instructor = instructor
                original_demo.scheduled_at = scheduled_at
                original_demo.meeting_link = meeting_link
                original_demo.status = DemoSchedule.STATUS_RESCHEDULED
                original_demo.save(update_fields=['instructor', 'scheduled_at', 'meeting_link', 'status'])
                logger.info(
                    "Demo rescheduled in place: id=%s campaign=%s instructor=%s leads=%s created_by=%s",
                    original_demo.id,
                    original_demo.campaign.id,
                    instructor.id,
                    total_leads,
                    request.user.id,
                )
        except Exception as exc:
            logger.exception(
                "Failed to reschedule demo %s: %s",
                pk,
                exc,
            )
            return Response(
                {"error": "Failed to reschedule demo"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Send emails to rescheduled leads (async)
        try:
            send_demo_reschedule_emails(original_demo.id, original_demo_data)
        except Exception as exc:
            logger.exception(
                "Failed to send reschedule demo emails for demo %s: %s",
                original_demo.id,
                exc,
            )

        response_serializer = DemoScheduleSerializer(
            original_demo,
            context={'request': request}
        )
        return Response(
            {
                "message": "Demo rescheduled successfully",
                "non_attended_leads_count": total_leads,
                "demo_schedule": response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class DemoScheduleStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            demo_schedule = DemoSchedule.objects.get(pk=pk)
        except DemoSchedule.DoesNotExist:
            return Response({"error": "Demo schedule not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "id": demo_schedule.id,
                "status": demo_schedule.status,
            },
            status=status.HTTP_200_OK,
        )
