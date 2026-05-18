from django.urls import path
from .views import (
    EnrollView,
    EnrollmentListView,
    ApproveEnrollmentView,
    RejectEnrollmentView,
    CreateOrderView,
    VerifyPaymentView,
    StudentCoursesView,
    StudentDashboardStatsView,
    EnrollmentDetailCRUDView,
    FeeStatusChoicesView,
    StatusChoicesView,
    CourseTypeChoicesView,
    ModeChoicesView,
    TimingChoicesView,
    ExperienceChoicesView,
    CurrentStatusChoicesView
)

urlpatterns = [
    path('Student/', EnrollView.as_view()),
    path('student/courses/', StudentCoursesView.as_view()),
    path('student/dashboard-stats/', StudentDashboardStatsView.as_view()),
    path('', EnrollmentListView.as_view()),
    path('<int:id>/', EnrollmentDetailCRUDView.as_view()), # CRUD operations
    path('<int:id>/approve/', ApproveEnrollmentView.as_view()),
    path('<int:id>/reject/', RejectEnrollmentView.as_view()),
    path('create-order/', CreateOrderView.as_view()),
    path('verify-payment/', VerifyPaymentView.as_view()), 
    
    # Choice URLs
    path('choices/fee-status/', FeeStatusChoicesView.as_view()),
    path('choices/status/', StatusChoicesView.as_view()),
    path('choices/course-type/', CourseTypeChoicesView.as_view()),
    path('choices/mode/', ModeChoicesView.as_view()),
    path('choices/timing/', TimingChoicesView.as_view()),
    path('choices/experience/', ExperienceChoicesView.as_view()),
    path('choices/current-status/', CurrentStatusChoicesView.as_view()),
]
