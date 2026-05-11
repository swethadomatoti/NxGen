from django.conf import settings
from django.db import models


class DemoSchedule(models.Model):
    STATUS_SCHEDULED = 'scheduled'
    STATUS_ATTENDED = 'attended'
    STATUS_RESCHEDULED = 'rescheduled'
    STATUS_COMPLETED = 'completed'

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_ATTENDED, 'Attended'),
        (STATUS_RESCHEDULED, 'Rescheduled'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    campaign = models.ForeignKey(
        'campaign.Campaign',
        on_delete=models.CASCADE,
        related_name='demo_schedules',
    )
    instructor = models.ForeignKey(
        'instructors.Instructor',
        on_delete=models.CASCADE,
        related_name='demo_schedules',
    )
    parent_demo = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reschedules',
    )
    leads = models.ManyToManyField(
        'LeadManagement.Lead',
        related_name='demo_schedules',
        blank=True,
    )
    scheduled_at = models.DateTimeField()
    meeting_link = models.URLField(max_length=500)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,    
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_demo_schedules',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_at']

    def __str__(self):
        return f"Demo for {self.campaign.name} at {self.scheduled_at.isoformat()}"

    def get_root_schedule(self):
        demo = self
        while demo.parent_demo is not None:
            demo = demo.parent_demo
        return demo

    def get_schedule_chain(self):
        root = self.get_root_schedule()
        chain = []
        queue = [root]

        while queue:
            schedule = queue.pop(0)
            if schedule.pk in {item.pk for item in chain}:
                continue
            chain.append(schedule)
            queue.extend(list(schedule.reschedules.all()))

        return chain

    def get_all_leads(self):
        from LeadManagement.models import Lead

        schedule_ids = [schedule.pk for schedule in self.get_schedule_chain()]
        return Lead.objects.filter(demo_schedules__in=schedule_ids).distinct()

    def get_aggregated_attendance(self):
        from .models import DemoAttendance

        attendance_map = {}
        schedule_ids = [schedule.pk for schedule in self.get_schedule_chain()]
        for attendance in DemoAttendance.objects.filter(demo_schedule__in=schedule_ids):
            existing = attendance_map.get(attendance.lead_id)
            if existing is None:
                attendance_map[attendance.lead_id] = attendance
                continue

            if attendance.attended and not existing.attended:
                attendance_map[attendance.lead_id] = attendance
                continue

            if attendance.attended == existing.attended:
                if attendance.attended_at and (
                    not existing.attended_at or attendance.attended_at > existing.attended_at
                ):
                    attendance_map[attendance.lead_id] = attendance

        return attendance_map

    def update_status_after_attendance(self):
        total_leads = self.leads.count()
        attended_count = self.demo_attendances.filter(attended=True).count()

        if attended_count == 0:
            return

        if self.status == self.STATUS_RESCHEDULED and attended_count == total_leads:
            new_status = self.STATUS_COMPLETED
        else:
            new_status = self.STATUS_ATTENDED

        if self.status != new_status:
            self.status = new_status
            self.save(update_fields=['status'])


class DemoAttendance(models.Model):
    demo_schedule = models.ForeignKey(
        DemoSchedule,
        on_delete=models.CASCADE,
        related_name='demo_attendances',
    )
    lead = models.ForeignKey(
        'LeadManagement.Lead',
        on_delete=models.CASCADE,
        related_name='demo_attendances',
    )
    attended = models.BooleanField(default=False)
    attended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('demo_schedule', 'lead')

    def __str__(self):
        return f"{self.lead.fullname} attendance for demo {self.demo_schedule.id}: {self.attended}"
