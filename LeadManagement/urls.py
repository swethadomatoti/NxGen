from django.urls import path

from .views import LeadBulkImportView, LeadDetailView, LeadListCreateView, LeadStatusChoicesView

urlpatterns = [
    path('create-lead/', LeadListCreateView.as_view(), name='lead-list-create'),
    path('bulk-import/', LeadBulkImportView.as_view(), name='lead-bulk-import'),
    path('statuses/', LeadStatusChoicesView.as_view(), name='lead-status-choices'),
    path('lead/<int:pk>/', LeadDetailView.as_view(), name='lead-detail'),
]
