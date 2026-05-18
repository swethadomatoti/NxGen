from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from LeadManagement.models import Lead
from Demo.models import DemoSchedule
from campaign.models import Campaign
from enrollments.models import Enrollment
from accounts.permissions import IsAdminOnly

class DashboardStatsView(APIView):
    """
    View to provide summary statistics for the admin dashboard.
    Returns counts for leads, demos, campaigns, and enrollments.
    """
    permission_classes = [IsAdminOnly]

    def get(self, request):
        try:
            stats = {
                "leads_count": Lead.objects.count(),
                "demos_count": DemoSchedule.objects.count(),
                "campaigns_count": Campaign.objects.count(),
                "enrollments_count": Enrollment.objects.count(),
            }
            return Response(stats, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": "Failed to fetch dashboard stats", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
