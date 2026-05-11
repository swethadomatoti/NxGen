from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminOnly

from .models import Campaign
from .serializers import CampaignSerializer


class CampaignListCreateView(APIView):
    permission_classes = [IsAdminOnly]

    def get(self, request):
        campaigns = Campaign.objects.all()
        serializer = CampaignSerializer(campaigns, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CampaignSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid campaign data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response(
                {"error": "Failed to create campaign", "details": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CampaignStatusChoicesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        choices = [
            {"key": key, "label": label}
            for key, label in Campaign.STATUS_CHOICES
        ]
        return Response({"status_choices": choices}, status=status.HTTP_200_OK)


class CampaignDetailView(APIView):
    permission_classes = [IsAdminOnly]

    def get_campaign(self, pk):
        try:
            return Campaign.objects.get(pk=pk)
        except Campaign.DoesNotExist:
            return None

    def get(self, request, pk):
        campaign = self.get_campaign(pk)
        if campaign is None:
            return Response({"error": "Campaign not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CampaignSerializer(campaign)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        campaign = self.get_campaign(pk)
        if campaign is None:
            return Response({"error": "Campaign not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CampaignSerializer(campaign, data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid campaign data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {"error": "Failed to update campaign", "details": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, pk):
        campaign = self.get_campaign(pk)
        if campaign is None:
            return Response({"error": "Campaign not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CampaignSerializer(campaign, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid campaign data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {"error": "Failed to partially update campaign", "details": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        campaign = self.get_campaign(pk)
        if campaign is None:
            return Response({"error": "Campaign not found"}, status=status.HTTP_404_NOT_FOUND)

        campaign.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
