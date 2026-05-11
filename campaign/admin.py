from django.contrib import admin

from .models import Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'start_date', 'end_date')
    search_fields = ('name',)
    list_filter = ('status', 'start_date', 'end_date')
