from django.urls import path

from .views import (
    BulkDemoScheduleView,
    DemoScheduleListView,
    DemoScheduleDetailView,
    DemoScheduleAttendanceView,
    DemoScheduleLeadsView,
    RescheduleDemoView,
    DemoScheduleStatusView,
)

urlpatterns = [
    path('schedule/', BulkDemoScheduleView.as_view(), name='demo_schedule'),
    path('', DemoScheduleListView.as_view(), name='demo_schedule_list'),
    path('<int:pk>/', DemoScheduleDetailView.as_view(), name='demo_schedule_detail'),
    path('<int:pk>/leads/', DemoScheduleLeadsView.as_view(), name='demo_schedule_leads'),
    path('<int:pk>/attendance/', DemoScheduleAttendanceView.as_view(), name='demo_schedule_attendance'),
    path('<int:pk>/reschedule/', RescheduleDemoView.as_view(), name='demo_schedule_reschedule'),
    path('<int:pk>/status/', DemoScheduleStatusView.as_view(), name='demo_schedule_status'),
]
