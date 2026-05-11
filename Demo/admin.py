from django.contrib import admin

from .models import DemoSchedule


@admin.register(DemoSchedule)
class DemoScheduleAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'instructor', 'status', 'scheduled_at', 'created_by', 'created_at')
    list_filter = ('status', 'scheduled_at', 'campaign')
    search_fields = ('campaign__name', 'instructor__full_name', 'meeting_link')
