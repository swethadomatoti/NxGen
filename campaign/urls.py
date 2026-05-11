from django.urls import path

from .views import CampaignDetailView, CampaignListCreateView, CampaignStatusChoicesView

urlpatterns = [
    path('create_campaign/', CampaignListCreateView.as_view(), name='campaign-list-create'),
    path('statuses/', CampaignStatusChoicesView.as_view(), name='campaign-status-choices'),
    path('campaign/<int:pk>/', CampaignDetailView.as_view(), name='campaign-detail'),
]
