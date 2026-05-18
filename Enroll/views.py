from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Enrollment
from .serializers import EnrollmentSerializer


class EnrollmentListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [AllowAny()]  # Allow anyone to enroll
        return [IsAuthenticated()]

    def get(self, request):
        enrollments = Enrollment.objects.select_related('course').all()
        
        # Optional filtering by email or campaign_id
        email = request.query_params.get('email')
        if email:
            enrollments = enrollments.filter(email=email)
            
        campaign_id = request.query_params.get('campaign_id')
        if campaign_id:
            enrollments = enrollments.filter(lead__campaign_id=campaign_id)
            
        serializer = EnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = EnrollmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EnrollmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Enrollment.objects.select_related('course').get(pk=pk)
        except Enrollment.DoesNotExist:
            return None

    def get(self, request, pk):
        enrollment = self.get_object(pk)
        if enrollment is None:
            return Response({'detail': 'Enrollment not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = EnrollmentSerializer(enrollment)
        return Response(serializer.data)

    def put(self, request, pk):
        enrollment = self.get_object(pk)
        if enrollment is None:
            return Response({'detail': 'Enrollment not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = EnrollmentSerializer(enrollment, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        enrollment = self.get_object(pk)
        if enrollment is None:
            return Response({'detail': 'Enrollment not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = EnrollmentSerializer(enrollment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        enrollment = self.get_object(pk)
        if enrollment is None:
            return Response({'detail': 'Enrollment not found.'}, status=status.HTTP_404_NOT_FOUND)
        enrollment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


from Demo.models import DemoAttendance

class AttendedLeadsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        campaign_id = request.query_params.get('campaign_id')
        demo_id = request.query_params.get('demo_id')

        # Base queryset: only leads who attended
        attendances = DemoAttendance.objects.filter(attended=True).select_related('lead', 'demo_schedule', 'demo_schedule__campaign')

        if campaign_id:
            attendances = attendances.filter(demo_schedule__campaign_id=campaign_id)
        if demo_id:
            attendances = attendances.filter(demo_schedule_id=demo_id)

        # Exclude leads who are already enrolled in this course (optional)
        # For now, let's just return all attended leads
        
        data = []
        for att in attendances:
            lead = att.lead
            campaign = att.demo_schedule.campaign
            course = campaign.course
            
            # Check if lead is already enrolled in this course (if course exists)
            is_enrolled = False
            if course:
                is_enrolled = Enrollment.objects.filter(
                    email=lead.email,
                    course=course
                ).exists()

            if not is_enrolled:
                data.append({
                    "lead_id": lead.id,
                    "fullname": lead.fullname,
                    "email": lead.email,
                    "phone": lead.phone_number,
                    "course_id": course.id if course else None,
                    "course_title": course.title if course else None,
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "demo_id": att.demo_schedule.id,
                    "attended_at": att.attended_at
                })

        return Response(data)

class CourseTypeChoicesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in Enrollment.COURSE_TYPE_CHOICES])

class CurrentStatusChoicesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in Enrollment.CURRENT_STATUS_CHOICES])

class ModeChoicesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in Enrollment.MODE_CHOICES])

class TimingChoicesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in Enrollment.TIMING_CHOICES])

class ExperienceChoicesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in Enrollment.EXPERIENCE_CHOICES])

class FeeStatusChoicesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response([{"key": c[0], "label": c[1]} for c in Enrollment.FEE_STATUS_CHOICES])
