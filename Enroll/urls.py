from django.urls import path
from .views import (
    EnrollmentListCreateView,
    EnrollmentDetailView,
    CourseTypeChoicesView,
    CurrentStatusChoicesView,
    ModeChoicesView,
    TimingChoicesView,
    ExperienceChoicesView,
    FeeStatusChoicesView,
    AttendedLeadsListView,
)

urlpatterns = [
    path('attended-leads/', AttendedLeadsListView.as_view(), name='attended_leads_list'),
    path('course-types/', CourseTypeChoicesView.as_view(), name='course_type_choices'),
    path('current-status/', CurrentStatusChoicesView.as_view(), name='current_status_choices'),
    path('modes/', ModeChoicesView.as_view(), name='mode_choices'),
    path('timings/', TimingChoicesView.as_view(), name='timing_choices'),
    path('experience-levels/', ExperienceChoicesView.as_view(), name='experience_choices'),
    path('fee-statuses/', FeeStatusChoicesView.as_view(), name='fee_status_choices'),
    path('enrollments/', EnrollmentListCreateView.as_view(), name='enrollments_list_create'),
    path('enrollments/<int:pk>/', EnrollmentDetailView.as_view(), name='enrollment_detail'),
]
