from datetime import timedelta
import re

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.conf import settings
import random
import string
from .permissions import IsAdminOnly
from .tasks import (
    send_admin_enrollment_email_sync,
    send_student_approval_email_sync,
    send_student_rejection_email_sync,
)
import hmac
import hashlib
from django.utils import timezone
from .models import Enrollment, PaymentDetail
from .serializers import EnrollmentSerializer, PaymentDetailSerializer
from accounts.models import StudentProfile

import razorpay

from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors





User = get_user_model()


# ----------------ENROLL View---------------- #

class EnrollView(APIView):

    def post(self, request):
        courses = request.data.get('courses')
        course = request.data.get('course')

        if courses and isinstance(courses, list):
            course_list = courses
        elif course:
            course_list = [course]
        else:
            return Response({"error": "No course provided."}, status=status.HTTP_400_BAD_REQUEST)

        created_enrollments = []
        errors = []
        email_warnings = []

        for c in course_list:
            data = request.data.copy()
            data['course'] = c
            if 'courses' in data:
                del data['courses']

            serializer = EnrollmentSerializer(data=data)

            if serializer.is_valid():
                try: 
                    enrollment = serializer.save()

                    try:
                        send_admin_enrollment_email_sync(
                            enrollment.name,
                            enrollment.email,
                            enrollment.course.title,
                            enrollment.phone
                        )
                    except Exception as email_error:
                        email_warnings.append(f"Notification error for {c}: {str(email_error)}")

                    created_enrollments.append(enrollment)
                except Exception as e:
                    errors.append({"course": c, "error": "Failed to create enrollment", "details": str(e)})
            else:
                errors.append({"course": c, "errors": serializer.errors})

        if errors and not created_enrollments:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        # Build response payload
        payload = {
            "message": "Enrollment successful",
            "enrollments": [e.id for e in created_enrollments],
            "redirect": "payment"
        }
        
        # Maintain backward compatibility for single course response
        if len(created_enrollments) == 1:
            payload["enrollment_id"] = created_enrollments[0].id
            
        if email_warnings:
            payload["warnings"] = email_warnings
        if errors:
            payload["errors"] = errors
            return Response(payload, status=status.HTTP_207_MULTI_STATUS)

        return Response(payload, status=status.HTTP_201_CREATED)

   

    
# ---------------- Enrollment LIST ---------------- #

class EnrollmentListView(APIView):
    def get(self, request):
        enrollments = Enrollment.objects.all().order_by("-created_at")
        serializer = EnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)


# ---------------- APPROVE ---------------- #

class ApproveEnrollmentView(APIView):
    permission_classes = [IsAdminOnly]
    def post(self, request, id):
        try:
            enrollment = Enrollment.objects.get(id=id)
        except Enrollment.DoesNotExist:
            return Response({"error": "Enrollment not found"}, status=status.HTTP_404_NOT_FOUND)

        # ✅ Already approved check
        if enrollment.status == "approved":
            return Response({"message": "Already approved"}, status=status.HTTP_200_OK)

        try:
            enrollment.status = "approved"
            enrollment.is_active = True
            enrollment.save()

            return Response({
                "message": "Enrollment approved successfully. Confirmation email sent to student."
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": "Failed to approve enrollment", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ---------------- REJECT ---------------- #

class RejectEnrollmentView(APIView):
    permission_classes = [IsAdminOnly]

    def post(self, request, id):
        try:
            enrollment = Enrollment.objects.get(id=id)
        except Enrollment.DoesNotExist:
            return Response({"error": "Enrollment not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            # ✅ Check if already rejected
            if enrollment.status == "rejected":
                return Response({"message": "Already rejected"}, status=status.HTTP_200_OK)

            enrollment.status = "rejected"
            enrollment.save()

            email_warning = None
            try:
                send_student_rejection_email_sync(
                    enrollment.name,
                    enrollment.course.title,
                    enrollment.email
                )
            except Exception as email_error:
                email_warning = f"Enrollment rejected, but student email failed: {str(email_error)}"

            payload = {"message": "Enrollment rejected successfully."}
            if email_warning:
                payload["warning"] = email_warning
            else:
                payload["message"] = "Enrollment rejected successfully. Student has been notified."

            return Response(payload, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": "Failed to reject enrollment", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



#_________________________________________________
#           Razorpay
#_________________________________________________


class CreateOrderView(APIView):

    def post(self, request):
        amount = request.data.get("amount")  # in rupees
        enrollment_id = request.data.get("enrollment_id")

        if enrollment_id:
            try:
                enrollment = Enrollment.objects.get(id=enrollment_id)
                if enrollment.status != 'approved':
                    return Response(
                        {"error": "Payment can only be initiated for approved enrollments."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                # If no amount is provided, default to the course price or remaining balance
                if not amount:
                    payment_detail = enrollment.payment_details.first()
                    if payment_detail and payment_detail.remaining_balance > 0:
                        amount = payment_detail.remaining_balance
                    elif enrollment.course and enrollment.course.price:
                        amount = enrollment.course.price
            except Enrollment.DoesNotExist:
                return Response({"error": "Enrollment not found."}, status=status.HTTP_404_NOT_FOUND)

        if not amount:
            return Response({"error": "Amount is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = razorpay.Client(auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET
            ))

            order = client.order.create({
                "amount": int(float(amount) * 100),  # convert to paisa securely
                "currency": "INR",
                "payment_capture": 1
            })

            return Response({
                "order_id": order["id"],
                "amount": order["amount"],
                "key": settings.RAZORPAY_KEY_ID
            })
        except razorpay.errors.BadRequestError as e:
            return Response(
                {"error": f"Razorpay Bad Request: {str(e)}", "details": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": "Failed to create order", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )





class VerifyPaymentView(APIView):

    def post(self, request):
        data = request.data

        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_signature = data.get("razorpay_signature")
        enrollment_id = data.get("enrollment_id")
        enrollment_ids = data.get("enrollment_ids")

        # 🔒 Generate signature
        generated_signature = hmac.new(
            bytes(settings.RAZORPAY_KEY_SECRET, 'utf-8'),
            bytes(f"{razorpay_order_id}|{razorpay_payment_id}", 'utf-8'),
            hashlib.sha256
        ).hexdigest()

        # ✅ Verify payment
        if generated_signature == razorpay_signature:
            # Handle multiple or single enrollments
            ids_to_update = enrollment_ids if enrollment_ids else ([enrollment_id] if enrollment_id else [])
            
            if not ids_to_update:
                return Response({"error": "No enrollment ID provided"}, status=400)

            # 🔥 Fetch secure order details directly from Razorpay
            try:
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                order_info = client.order.fetch(razorpay_order_id)
                amount_paid = order_info.get("amount", 0) / 100.0  # convert paisa to rupees
            except Exception:
                amount_paid = data.get("amount") # fallback to frontend payload if fetch fails

            updated = 0
            for e_id in ids_to_update:
                try:
                    enrollment = Enrollment.objects.get(id=e_id)
                    # 🔥 Update enrollment
                    enrollment.payment_status = "paid"
                    enrollment.razorpay_order_id = razorpay_order_id
                    enrollment.razorpay_payment_id = razorpay_payment_id
                    enrollment.save()
                    
                    # 🔥 Update PaymentDetail
                    payment_detail, _ = PaymentDetail.objects.get_or_create(enrollment=enrollment)
                    if amount_paid:
                        payment_detail.payment_paid = float(payment_detail.payment_paid) + float(amount_paid)
                    else:
                        payment_detail.payment_paid = float(payment_detail.fee_amount) if payment_detail.fee_amount else float(enrollment.course.price)
                    payment_detail.save()
                    
                    updated += 1
                except Enrollment.DoesNotExist:
                    continue

            return Response({
                "message": f"Payment verified & {updated} enrollment(s) updated"
            })

        else:
            return Response({
                "error": "Payment verification failed"
            }, status=400)

#**********Student CoursesView**********************
           
from rest_framework.permissions import IsAuthenticated
from .serializers import StudentEnrolledCourseSerializer
from learning.models import LessonProgress
from courses.models import Batch

class StudentCoursesView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        email = request.user.email
        enrollments = Enrollment.objects.filter(email=email, status='approved', is_active=True)
        serializer = StudentEnrolledCourseSerializer(enrollments, many=True, context={'request': request})
        return Response(serializer.data)
#----------------------------------------------
# StudentDashboardStatsView
#----------------------------------------------
class StudentDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        email = request.user.email
        enrolled_count = Enrollment.objects.filter(email=email, status='approved', is_active=True).count()
        completed_lessons = LessonProgress.objects.filter(student=request.user, completed=True).count()
        
        active_batches = Batch.objects.filter(students=request.user, is_live_class_active=True)
        active_live_classes = []
        for b in active_batches:
            active_live_classes.append({
                'course_title': b.course.title,
                'batch_name': b.name,
                'live_link': b.live_link
            })
            
        return Response({
            'enrolled_courses_count': enrolled_count,
            'completed_lessons_count': completed_lessons,
            'next_live_session': 'Saturday, 10:00 AM',
            'active_live_classes': active_live_classes
        })

# ---------------- CHOICE VIEWS ---------------- #

class FeeStatusChoicesView(APIView):
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in [
            ('Pending', 'Pending'),
            ('Paid', 'Paid'),
            ('Partially Paid', 'Partially Paid'),
        ]])

class StatusChoicesView(APIView):
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in Enrollment.STATUS_CHOICES])

class CourseTypeChoicesView(APIView):
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in Enrollment.COURSE_TYPE_CHOICES])

class ModeChoicesView(APIView):
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in Enrollment.MODE_CHOICES])

class TimingChoicesView(APIView):
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in Enrollment.TIMING_CHOICES])

class ExperienceChoicesView(APIView):
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in Enrollment.EXPERIENCE_CHOICES])

class CurrentStatusChoicesView(APIView):
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in Enrollment.CURRENT_STATUS_CHOICES])

# ---------------- DETAIL CRUD ---------------- #

class EnrollmentDetailCRUDView(APIView):
    def get_object(self, id):
        try:
            return Enrollment.objects.get(id=id)
        except Enrollment.DoesNotExist:
            return None

    def get(self, request, id):
        enrollment = self.get_object(id)
        if not enrollment:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = EnrollmentSerializer(enrollment)
        return Response(serializer.data)

    def put(self, request, id):
        enrollment = self.get_object(id)
        if not enrollment:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = EnrollmentSerializer(enrollment, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, id):
        enrollment = self.get_object(id)
        if not enrollment:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = EnrollmentSerializer(enrollment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        enrollment = self.get_object(id)
        if not enrollment:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        enrollment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------- PAYMENT DETAILS CRUD ---------------- #

class EnrollmentPaymentDetailView(APIView):
    def get(self, request, enrollment_id):
        try:
            enrollment = Enrollment.objects.get(id=enrollment_id)
        except Enrollment.DoesNotExist:
            return Response({"error": "Enrollment not found"}, status=status.HTTP_404_NOT_FOUND)
            
        # Get existing payment details or create a default one (which triggers auto-calculation of fees)
        payment, created = PaymentDetail.objects.get_or_create(enrollment=enrollment)
        
        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data)

    def post(self, request, enrollment_id):
        try:
            enrollment = Enrollment.objects.get(id=enrollment_id)
        except Enrollment.DoesNotExist:
            return Response({"error": "Enrollment not found"}, status=status.HTTP_404_NOT_FOUND)
            
        payment = PaymentDetail.objects.filter(enrollment=enrollment).first()
        
        if payment:
            # Update existing
            serializer = PaymentDetailSerializer(payment, data=request.data, partial=True)
        else:
            # Create new
            data = request.data.copy()
            data['enrollment'] = enrollment.id
            serializer = PaymentDetailSerializer(data=data)
            
        if serializer.is_valid():
            serializer.save()
            # Also update the enrollment fee status if needed
            if 'payment_paid' in request.data:
                # Basic logic to update fee_status based on payment
                try:
                    paid = float(serializer.instance.payment_paid)
                    fee = float(serializer.instance.fee_amount)
                    if paid >= fee and fee > 0:
                        enrollment.fee_status = 'Paid'
                    elif paid > 0:
                        enrollment.fee_status = 'Partially Paid'
                    else:
                        enrollment.fee_status = 'Pending'
                    enrollment.save(update_fields=['fee_status'])
                except (ValueError, TypeError):
                    pass
                    
            return Response(serializer.data, status=status.HTTP_200_OK if payment else status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, enrollment_id):
        payment = PaymentDetail.objects.filter(enrollment_id=enrollment_id).first()
        if not payment:
            return Response({"error": "Payment details not found"}, status=status.HTTP_404_NOT_FOUND)
            
        serializer = PaymentDetailSerializer(payment, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, enrollment_id):
        payment = PaymentDetail.objects.filter(enrollment_id=enrollment_id).first()
        if not payment:
            return Response({"error": "Payment details not found"}, status=status.HTTP_404_NOT_FOUND)
            
        serializer = PaymentDetailSerializer(payment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, enrollment_id):
        payment = PaymentDetail.objects.filter(enrollment_id=enrollment_id).first()
        if not payment:
            return Response({"error": "Payment details not found"}, status=status.HTTP_404_NOT_FOUND)
            
        payment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------- INVOICE ---------------- #

class GenerateInvoiceView(APIView):
    def get(self, request, enrollment_id):
        try:
            enrollment = Enrollment.objects.get(id=enrollment_id)
        except Enrollment.DoesNotExist:
            return Response({"error": "Enrollment not found"}, status=status.HTTP_404_NOT_FOUND)
            
        payment = PaymentDetail.objects.filter(enrollment=enrollment).first()
        
        # Determine format (json or pdf) - use 'export' as parameter to avoid DRF format conflicts
        output_format = request.query_params.get('export', 'json')
        
        # Use enrollment creation date to ensure the invoice number and date stay the same on every download
        base_date = enrollment.created_at if enrollment.created_at else timezone.now()
        
        invoice_number = f"INV-{enrollment.id}-{base_date.strftime('%Y%m%d%H%M%S')}"
        invoice_date = base_date.strftime("%Y-%m-%d %H:%M:%S")
        
        total_fee = payment.fee_amount if payment else (enrollment.course.price if enrollment.course else 0)
        amount_paid = payment.payment_paid if payment else 0
        balance_remaining = payment.remaining_balance if payment else (enrollment.course.price if enrollment.course else 0)
        
        if output_format.lower() == 'pdf':
            # Generate PDF
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="Invoice_{invoice_number}.pdf"'
            
            p = canvas.Canvas(response, pagesize=letter)
            width, height = letter
            
            # Title
            p.setFont("Helvetica-Bold", 24)
            p.drawString(50, height - 50, "INVOICE")
            
            # Company Details (Placeholder)
            p.setFont("Helvetica", 10)
            p.drawString(50, height - 70, "Your Company Name")
            p.drawString(50, height - 85, "123 Business Road, City, Country")
            
            # Invoice Info
            p.setFont("Helvetica-Bold", 12)
            p.drawString(350, height - 50, f"Invoice No: {invoice_number}")
            p.setFont("Helvetica", 10)
            p.drawString(350, height - 65, f"Date: {invoice_date}")
            p.drawString(350, height - 80, f"Status: {enrollment.fee_status}")
            
            # Separator Line
            p.setStrokeColor(colors.grey)
            p.line(50, height - 100, width - 50, height - 100)
            
            # Student Details
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, height - 130, "Billed To:")
            p.setFont("Helvetica", 10)
            p.drawString(50, height - 145, f"Name: {enrollment.name}")
            p.drawString(50, height - 160, f"Email: {enrollment.email}")
            p.drawString(50, height - 175, f"Phone: {enrollment.phone}")
            
            # Course Details Section
            y_position = height - 230
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, y_position, "Course Details")
            p.line(50, y_position - 5, width - 50, y_position - 5)
            
            p.setFont("Helvetica", 10)
            y_position -= 25
            course_title = enrollment.course.title if enrollment.course else 'N/A'
            p.drawString(50, y_position, f"Title: {course_title}")
            y_position -= 15
            p.drawString(50, y_position, f"Type: {getattr(enrollment, 'course_type', 'N/A')}")
            y_position -= 15
            p.drawString(50, y_position, f"Mode: {getattr(enrollment, 'preferred_mode', 'N/A')}")
            
            # Payment Details Section
            y_position -= 40
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, y_position, "Payment Summary")
            p.line(50, y_position - 5, width - 50, y_position - 5)
            
            p.setFont("Helvetica", 10)
            y_position -= 25
            p.drawString(50, y_position, "Total Course Fee:")
            p.drawString(200, y_position, f"Rs. {total_fee}")
            
            y_position -= 15
            p.drawString(50, y_position, "Amount Paid:")
            p.drawString(200, y_position, f"Rs. {amount_paid}")
            
            y_position -= 20
            p.setFont("Helvetica-Bold", 10)
            p.drawString(50, y_position, "Balance Remaining:")
            p.drawString(200, y_position, f"Rs. {balance_remaining}")
            
            # Transaction Info
            y_position -= 40
            p.setFont("Helvetica", 9)
            p.drawString(50, y_position, "Transaction Info:")
            if enrollment.razorpay_payment_id:
                y_position -= 12
                p.drawString(50, y_position, f"Payment ID: {enrollment.razorpay_payment_id}")
            if enrollment.razorpay_order_id:
                y_position -= 12
                p.drawString(50, y_position, f"Order ID: {enrollment.razorpay_order_id}")
            
            # Footer
            p.setFont("Helvetica-Oblique", 8)
            p.drawString(50, 50, "Thank you for joining our course!")
            
            p.showPage()
            p.save()
            return response
            
        else:
            # Generate JSON Output
            invoice_data = {
                "invoice_number": invoice_number,
                "date": invoice_date,
                "student_details": {
                    "name": enrollment.name,
                    "email": enrollment.email,
                    "phone": enrollment.phone
                },
                "course_details": {
                    "title": enrollment.course.title if enrollment.course else None,
                    "type": getattr(enrollment, 'course_type', None),
                    "mode": getattr(enrollment, 'preferred_mode', None)
                },
                "payment_details": {
                    "total_fee": total_fee,
                    "amount_paid": amount_paid,
                    "balance_remaining": balance_remaining,
                    "payment_status": enrollment.payment_status,
                    "fee_status": enrollment.fee_status,
                },
                "transaction_details": {
                    "razorpay_order_id": enrollment.razorpay_order_id,
                    "razorpay_payment_id": enrollment.razorpay_payment_id,
                }
            }
            
            return Response(invoice_data, status=status.HTTP_200_OK)


from django.db.models import Q

class PaidInvoicesListView(APIView):
    def get(self, request):
        # Fetch enrollments where a payment has been made
        enrollments = Enrollment.objects.filter(
            Q(fee_status__in=['Paid', 'Partially Paid']) | 
            Q(payment_status__iexact='paid') | 
            Q(payment_details__payment_paid__gt=0)
        ).distinct().order_by('-created_at')

        data = []
        for enrollment in enrollments:
            payment = enrollment.payment_details.first()
            base_date = enrollment.created_at if enrollment.created_at else timezone.now()
            
            data.append({
                "enrollment_id": enrollment.id,
                "invoice_number": f"INV-{enrollment.id}-{base_date.strftime('%Y%m%d%H%M%S')}",
                "student_name": enrollment.name,
                "student_email": enrollment.email,
                "course_title": enrollment.course.title if enrollment.course else "N/A",
                "amount_paid": payment.payment_paid if payment else 0,
                "balance_remaining": payment.remaining_balance if payment else (enrollment.course.price if enrollment.course else 0),
                "fee_status": enrollment.fee_status,
                "download_pdf_url": f"/api/enrollments/{enrollment.id}/invoice/?export=pdf",
                "json_details_url": f"/api/enrollments/{enrollment.id}/invoice/"
            })
        
        return Response(data, status=status.HTTP_200_OK)

