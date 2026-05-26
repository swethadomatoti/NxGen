import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()
from enrollments.views import CreateOrderView
from enrollments.models import Enrollment
from rest_framework.test import APIRequestFactory

def run():
    factory = APIRequestFactory()
    request = factory.post('/api/enrollments/create-order/', {
        "enrollment_id": 8, "amount": 0
    }, format='json')
    view = CreateOrderView.as_view()
    response = view(request)
    print(response.data)

if __name__ == '__main__':
    run()