import os
import sys
import django

# Add the project directory to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from campaign.models import Campaign
from Demo.models import DemoSchedule
from Enroll.models import Enrollment

demo_id = 53
try:
    demo = DemoSchedule.objects.get(id=demo_id)
    print(f"DEMO {demo_id}: Campaign={demo.campaign.name}, Course={demo.campaign.course}")
    
    course = demo.campaign.course
    if course:
        print(f"COURSE ID: {course.id}, TITLE: {course.title}")
        
        # Check enrollments
        for lead in demo.leads.all():
            is_enrolled = Enrollment.objects.filter(email=lead.email, course=course).exists()
            print(f"LEAD: {lead.email}, ENROLLED: {is_enrolled}")
    else:
        print("NO COURSE LINKED TO THIS CAMPAIGN")
except Exception as e:
    print(f"ERROR: {e}")
