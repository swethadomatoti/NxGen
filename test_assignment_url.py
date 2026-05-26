import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()
from courses.models import Assignment
assignment = Assignment.objects.exclude(file='').first()
if assignment:
    print(f"Assignment: {assignment.assignment_title}")
    # print(f"Default URL: {assignment.file.url}")
    from courses.storage import get_signed_url
    print(f"Signed URL: {get_signed_url(assignment.file.name)}")
else:
    print("No assignment with file found.")