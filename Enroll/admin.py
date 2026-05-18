from django.contrib import admin
from .models import Enrollment


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'email', 'course', 'course_type', 'fee_status', 'enrollment_date', 'created_at')
    list_filter = ('course_type', 'fee_status', 'course', 'preferred_mode')
    search_fields = ('full_name', 'email', 'phone_number', 'course__title', 'organization')
