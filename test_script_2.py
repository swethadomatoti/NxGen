import os
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.contrib.auth import get_user_model
from enrollments.views import StudentCoursesView
from rest_framework.test import APIRequestFactory, force_authenticate

def run():
    User = get_user_model()
    user = User.objects.filter(email='swethadomatoti@test.com').first()
    if user:
        factory = APIRequestFactory()
        request = factory.get('/')
        request.user = user
        force_authenticate(request, user=user)
        response = StudentCoursesView.as_view()(request)
        print(json.dumps(response.data, indent=2))
        
if __name__ == '__main__':
    run()