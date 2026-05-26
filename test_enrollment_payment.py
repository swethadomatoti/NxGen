import os
import django
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from enrollments.models import Enrollment
from courses.models import Course
from django.contrib.auth import get_user_model

User = get_user_model()

def run_test():
    # 1. Ensure course exists
    course, _ = Course.objects.get_or_create(
        title="SAP BTP",
        defaults={
            "description": "SAP BTP Course",
            "price": 5000.00,
        }
    )
    print(f"Course: {course.title}, Price: {course.price}")

    # 2. Create or get student enrollment
    enrollment, created = Enrollment.objects.get_or_create(
        email="swethadomatoti@test.com",
        course=course,
        defaults={
            "name": "swethadomatoti",
            "phone": "9876543210",
            "course_type": "Training",
            "qualification": "BTech",
            "current_status": "Student",
            "preferred_mode": "Online",
            "preferred_timing": "Morning",
            "experience_level": "Beginner",
            "status": "approved", # Approve the enrollment directly for the test
        }
    )
    
    if not created and enrollment.status != "approved":
        enrollment.status = "approved"
        enrollment.save()
        
    print(f"Enrollment: {enrollment.name}, Status: {enrollment.status}, ID: {enrollment.id}")

    # 3. Simulate API call for Creating Order
    from rest_framework.test import APIRequestFactory
    from enrollments.views import CreateOrderView

    factory = APIRequestFactory()
    request = factory.post('/api/enrollments/create-order/', {
        "enrollment_id": enrollment.id
    }, format='json')

    view = CreateOrderView.as_view()
    response = view(request)
    
    print("\n--- Create Order Response ---")
    print(f"Status Code: {response.status_code}")
    print(f"Data: {response.data}")

if __name__ == '__main__':
    run_test()
