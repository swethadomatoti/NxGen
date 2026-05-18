import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from campaign.models import Campaign
from Demo.models import DemoSchedule

demo_id = 53
try:
    demo = DemoSchedule.objects.get(id=demo_id)
    print(f"DEMO {demo_id}: Campaign={demo.campaign.name}, Course={demo.campaign.course}")
    if demo.campaign.course:
        print(f"COURSE ID: {demo.campaign.course.id}, TITLE: {demo.campaign.course.title}")
    else:
        print("NO COURSE LINKED TO THIS CAMPAIGN")
except Exception as e:
    print(f"ERROR: {e}")
