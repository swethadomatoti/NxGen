import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from LeadManagement.models import Lead

email = "swethadomatoti3@gmail.com"
lead = Lead.objects.filter(email=email).first()

if lead:
    print(f"FOUND LEAD: ID={lead.id}, Name={lead.fullname}, Email={lead.email}")
else:
    print(f"NO LEAD FOUND for email: {email}")
    # Let's list some leads to see what's there
    print("Recent leads:")
    for l in Lead.objects.all()[:5]:
        print(f"ID={l.id}, Email={l.email}")
