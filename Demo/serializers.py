from rest_framework import serializers
from django.urls import reverse
from django.utils import timezone
import pytz

from campaign.models import Campaign
from instructors.models import Instructor
from .models import DemoSchedule


class DemoScheduleCreateSerializer(serializers.Serializer):
    campaign = serializers.CharField(required=False, allow_blank=True)
    campaign_id = serializers.IntegerField(required=False)
    instructor = serializers.CharField(required=False, allow_blank=True)
    instructor_id = serializers.IntegerField(required=False)
    date = serializers.DateField()
    time = serializers.TimeField()
    link = serializers.URLField(max_length=500, required=False)
    meeting_link = serializers.URLField(max_length=500, required=False)

    def validate(self, attrs):
        campaign_identifier = attrs.get('campaign_id') or attrs.get('campaign')
        instructor_identifier = attrs.get('instructor_id') or attrs.get('instructor')
        meeting_link = attrs.get('meeting_link') or attrs.get('link')

        if campaign_identifier in (None, ''):
            raise serializers.ValidationError({'campaign': 'Campaign or campaign_id is required.'})
        if instructor_identifier in (None, ''):
            raise serializers.ValidationError({'instructor': 'Instructor or instructor_id is required.'})
        if not meeting_link:
            raise serializers.ValidationError({'link': 'Link or meeting_link is required.'})

        campaign = self._resolve_campaign(campaign_identifier)
        instructor = self._resolve_instructor(instructor_identifier)

        attrs['campaign_id'] = campaign.id
        attrs['instructor_id'] = instructor.id
        attrs['meeting_link'] = meeting_link
        return attrs

    def _resolve_campaign(self, value):
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            campaign = Campaign.objects.filter(pk=int(value)).first()
        else:
            campaign = Campaign.objects.filter(name__iexact=str(value).strip()).first()

        if campaign is None:
            raise serializers.ValidationError({'campaign': 'Campaign not found.'})
        return campaign

    def _resolve_instructor(self, value):
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            instructor = Instructor.objects.filter(pk=int(value)).first()
        else:
            instructor = Instructor.objects.filter(full_name__iexact=str(value).strip()).first()

        if instructor is None:
            raise serializers.ValidationError({'instructor': 'Instructor not found.'})
        return instructor


class DemoScheduleSerializer(serializers.ModelSerializer):
    campaign = serializers.SerializerMethodField()
    instructor = serializers.SerializerMethodField()
    link = serializers.SerializerMethodField()
    scheduled_at = serializers.SerializerMethodField()
    total_leads = serializers.SerializerMethodField()
    attended_count = serializers.SerializerMethodField()
    leads = serializers.SerializerMethodField()

    class Meta:
        model = DemoSchedule
        fields = [
            'id', 'campaign', 'instructor', 'link',
            'scheduled_at', 'status', 'total_leads', 'attended_count', 'leads'
        ]
        read_only_fields = ['id']

    def get_campaign(self, obj):
        return obj.campaign.name

    def get_instructor(self, obj):
        return obj.instructor.full_name

    def get_link(self, obj):
        return obj.meeting_link

    def get_scheduled_at(self, obj):
        scheduled_time = obj.scheduled_at
        return scheduled_time.strftime('%Y-%m-%d %H:%M:%S')

    def get_total_leads(self, obj):
        return obj.get_all_leads().count()

    def get_attended_count(self, obj):
        return sum(1 for attendance in obj.get_aggregated_attendance().values() if attendance.attended)

    def get_lead_attendance_url(self, obj):
        url = reverse('demo_schedule_attendance', kwargs={'pk': obj.id})
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_leads(self, obj):
        attendance_map = obj.get_aggregated_attendance()
        attendance_url = self.get_lead_attendance_url(obj)

        leads = []
        for lead in obj.get_all_leads():
            attendance = attendance_map.get(lead.id)
            attended_at = None
            attended = False
            if attendance is not None:
                attended = attendance.attended
                if attendance.attended_at is not None:
                    attended_at = attendance.attended_at.strftime('%Y-%m-%d %H:%M:%S')

            leads.append({
                'id': lead.id,
                'fullname': lead.fullname,
                'email': lead.email,
                'attended': attended,
                'attended_at': attended_at,
                'attendance_url': attendance_url,
            })
        return leads


class DemoScheduleAttendanceItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    attended = serializers.BooleanField()


class DemoScheduleAttendanceSerializer(serializers.Serializer):
    attendance = DemoScheduleAttendanceItemSerializer(many=True)

    def validate(self, attrs):
        lead_ids = [item['id'] for item in attrs['attendance']]
        if len(lead_ids) != len(set(lead_ids)):
            raise serializers.ValidationError({'attendance': 'Duplicate id values are not allowed.'})
        return attrs


class DemoScheduleLeadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    fullname = serializers.CharField()
    email = serializers.EmailField()
    attended = serializers.BooleanField()
    attended_at = serializers.CharField(allow_null=True)
    attendance_url = serializers.CharField()


class DemoScheduleUpdateSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()
    link = serializers.URLField(max_length=500, required=False)
    meeting_link = serializers.URLField(max_length=500, required=False)

    def validate(self, attrs):
        meeting_link = attrs.get('meeting_link') or attrs.get('link')
        if not meeting_link:
            raise serializers.ValidationError({'link': 'Link or meeting_link is required.'})
        attrs['meeting_link'] = meeting_link
        return attrs


class RescheduleDemoSerializer(serializers.Serializer):
    """Serializer for rescheduling demo for non-attended leads"""
    instructor = serializers.CharField(required=False, allow_blank=True)
    instructor_id = serializers.IntegerField(required=False)
    date = serializers.DateField()
    time = serializers.TimeField()
    link = serializers.URLField(max_length=500, required=False)
    meeting_link = serializers.URLField(max_length=500, required=False)

    def validate(self, attrs):
        instructor_identifier = attrs.get('instructor_id') or attrs.get('instructor')
        meeting_link = attrs.get('meeting_link') or attrs.get('link')

        if instructor_identifier in (None, ''):
            raise serializers.ValidationError({'instructor': 'Instructor or instructor_id is required.'})
        if not meeting_link:
            raise serializers.ValidationError({'link': 'Link or meeting_link is required.'})

        instructor = self._resolve_instructor(instructor_identifier)
        attrs['instructor_id'] = instructor.id
        attrs['meeting_link'] = meeting_link
        return attrs

    def _resolve_instructor(self, value):
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            instructor = Instructor.objects.filter(pk=int(value)).first()
        else:
            instructor = Instructor.objects.filter(full_name__iexact=str(value).strip()).first()

        if instructor is None:
            raise serializers.ValidationError({'instructor': 'Instructor not found.'})
        return instructor
