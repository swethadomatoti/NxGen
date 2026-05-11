import os
import sys
import django

# Add current directory to path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from courses.models import Assignment

User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()

client = APIClient()
client.force_authenticate(user=admin)

def test_filter(params):
    print(f"Testing with params: {params}")
    response = client.get('/api/courses/instructor-assignments/', params)
    print(f"Status: {response.status_code}")
    print(f"Count: {len(response.data)}")
    if response.data:
        first = response.data[0]
        # Check if instructor_details is present
        details = first.get('assignment', {}).get('instructor_details')
        print(f"Instructor Details present: {details is not None}")
        if details:
            print(f"Instructor Name: {details.get('name')}")
    print("-" * 30)

# 1. No filters
test_filter({})

# 2. Filter by Instructor
test_filter({'instructor_id': 1})

# 3. Filter by Course
test_filter({'course_id': 1})

# 4. Filter by Batch
test_filter({'batch_id': 1})

# 5. Combined
test_filter({'instructor_id': 1, 'course_id': 1, 'batch_id': 1})
