from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('fullname', 'email', 'phone_number', 'status', 'created_at')
    search_fields = ('fullname', 'email', 'phone_number')
    list_filter = ('status',)
    ordering = ('-created_at',)
