import os
import django
import hmac
import hashlib
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.conf import settings
import razorpay
from enrollments.models import Enrollment, PaymentDetail
from enrollments.views import VerifyPaymentView
from rest_framework.test import APIRequestFactory

def run():
    print(f"Using Razorpay Key: {settings.RAZORPAY_KEY_ID}")
    
    # 1. Look up student enrollment ID 8
    try:
        e = Enrollment.objects.get(id=8)
        print(f"Testing for Student: {e.name} (ID: {e.id}), Course: {e.course.title}")
    except Enrollment.DoesNotExist:
        print("Enrollment ID 8 not found in DB! Will create test enrollment.")
        from courses.models import Course
        c, _ = Course.objects.get_or_create(title="SAP BTP", defaults={"price": 30000})
        e, _ = Enrollment.objects.get_or_create(id=8, defaults={
            "name": "Swetha Domatoti",
            "email": "swethadomatoti@gmail.com",
            "phone": "+918688328875",
            "course": c,
            "status": "approved",
            "fee_status": "Partially Paid"
        })
        # Mock payment detail
        p, _ = PaymentDetail.objects.get_or_create(enrollment=e, defaults={"fee_amount": 30000, "payment_paid": 2000, "remaining_balance": 28000})

    amount_to_pay = 5000  # Let's test paying ₹5,000 via checkout
    print(f"Initiating Razorpay Order for amount: Rs {amount_to_pay}")

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    # 2. Create Order globally using real test credentials
    order = client.order.create({
        "amount": amount_to_pay * 100,  # paise
        "currency": "INR",
        "payment_capture": 1
    })
    
    order_id = order['id']
    
    # 3. Simulate frontend receiving the payment ID from Razorpay window popup
    fake_payment_id = "pay_MockPaymentXYZ123"
    
    generated_signature = hmac.new(
        bytes(settings.RAZORPAY_KEY_SECRET, 'utf-8'),
        bytes(f"{order_id}|{fake_payment_id}", 'utf-8'),
        hashlib.sha256
    ).hexdigest()

    print("\n--- RAZORPAY REQUIRED DETAILS ---")
    print(f"Razorpay Order ID:    {order_id}")
    print(f"Razorpay Payment ID:  {fake_payment_id}")
    print(f"Generated Signature:  {generated_signature}")

    # 4. Hit Verification API internally like frontend does 
    print("\n--- POSTING TO VERIFY API ---")
    factory = APIRequestFactory()
    req = factory.post('/api/enrollments/verify-payment/', {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": fake_payment_id,
        "razorpay_signature": generated_signature,
        "enrollment_id": e.id
    }, format='json')
    
    view = VerifyPaymentView.as_view()
    resp = view(req)
    
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {json.dumps(resp.data, indent=2)}")

if __name__ == '__main__':
    run()