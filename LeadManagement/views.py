from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import timedelta
import re

from accounts.permissions import IsAdminOnly
from campaign.models import Campaign
from .models import Lead
from .serializers import LeadSerializer

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import xlrd
except ImportError:
    xlrd = None


class ColumnMapper:
    """
    Flexible column mapping that handles:
    - Case-insensitive matching
    - Space-insensitive matching
    - Multiple field name variations
    """
    
    FIELD_MAPPINGS = {
        'fullname': ['fullname', 'full_name', 'full name', 'name', 'participant name', 'student name'],
        'phone_number': ['phone_number', 'phone', 'mobile_number', 'mobile', 'mobile number', 'contact', 'phone_no'],
        'email': ['email', 'email_address', 'email address', 'e-mail', 'mail'],
        'status': ['status', 'lead status', 'lead_status'],
        'campaign': ['campaign', 'campaign_name', 'campaign name'],
    }
    
    @staticmethod
    def normalize_column_name(col_name):
        """Normalize column name: lowercase, remove extra spaces"""
        if col_name is None:
            return ''
        return re.sub(r'\s+', '_', str(col_name).strip().lower())
    
    @classmethod
    def find_field_index(cls, header, field_name):
        """
        Find column index for a given field.
        Returns None if not found.
        """
        valid_names = cls.FIELD_MAPPINGS.get(field_name, [])
        
        for idx, col in enumerate(header):
            normalized_col = cls.normalize_column_name(col)
            
            for valid_name in valid_names:
                if cls.normalize_column_name(valid_name) == normalized_col:
                    return idx
        
        return None
    
    @classmethod
    def map_header(cls, header):
        """
        Map all columns and return a dict with field names and their indices.
        """
        mapping = {}
        for field_name in ['fullname', 'phone_number', 'email', 'status', 'campaign']:
            idx = cls.find_field_index(header, field_name)
            if idx is not None:
                mapping[field_name] = idx
        
        return mapping


class CampaignHandler:
    """Handle campaign creation and retrieval"""
    
    @staticmethod
    def get_or_create_campaign(campaign_name):
        """
        Get existing campaign or create a new one.
        Returns Campaign instance or None if campaign_name is empty.
        
        For new campaigns, sets:
        - start_date: today
        - end_date: today + 30 days
        - status: 'upcoming'
        """
        if not campaign_name or campaign_name.strip() == '':
            return None
        
        campaign_name = campaign_name.strip()
        
        # Set default dates for new campaigns
        today = timezone.now().date()
        thirty_days_later = today + timedelta(days=30)
        
        campaign, created = Campaign.objects.get_or_create(
            name=campaign_name,
            defaults={
                'status': 'upcoming',
                'start_date': today,
                'end_date': thirty_days_later,
            }
        )
        return campaign


class LeadListCreateView(APIView):
    permission_classes = [IsAdminOnly]

    def get(self, request):
        leads = Lead.objects.all()
        serializer = LeadSerializer(leads, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = LeadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid lead data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LeadDetailView(APIView):
    permission_classes = [IsAdminOnly]

    def get_lead(self, pk):
        try:
            return Lead.objects.get(pk=pk)
        except Lead.DoesNotExist:
            return None

    def get(self, request, pk):
        lead = self.get_lead(pk)
        if lead is None:
            return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = LeadSerializer(lead)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        lead = self.get_lead(pk)
        if lead is None:
            return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = LeadSerializer(lead, data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid lead data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        lead = self.get_lead(pk)
        if lead is None:
            return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = LeadSerializer(lead, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid lead data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        lead = self.get_lead(pk)
        if lead is None:
            return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

        lead.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LeadBulkImportView(APIView):
    """
    Bulk import leads from Excel files (.xls/.xlsx).
    
    Features:
    - Flexible column mapping (case-insensitive, space-insensitive)
    - Dynamic campaign creation/association
    - Row-wise error collection (doesn't stop on first error)
    - Transaction-based atomicity
    - Bulk operations for performance
    """
    permission_classes = [IsAdminOnly]

    def post(self, request):
        # 1. Validate file upload
        excel_file = request.FILES.get('file')
        if excel_file is None:
            return Response(
                {"error": "Excel file is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Parse Excel file
        filename = excel_file.name.lower()
        rows = self._parse_excel_file(excel_file, filename)
        
        if isinstance(rows, Response):
            return rows
        
        if not rows:
            return Response(
                {"error": "Excel file is empty"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Extract and validate header
        header = self._normalize_header(rows[0])
        
        # 4. Map columns flexibly
        column_mapping = ColumnMapper.map_header(header)
        
        # Verify required fields are present
        required_fields = ['fullname', 'phone_number', 'email']
        missing_fields = [f for f in required_fields if column_mapping.get(f) is None]
        
        if missing_fields:
            return Response(
                {
                    "error": "Excel file is missing required columns",
                    "missing_fields": missing_fields,
                    "hint": "Required columns: Full Name, Phone Number, Email (case-insensitive)",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 5. Process rows with transaction
        import_result = self._process_rows(rows[1:], column_mapping)
        
        return import_result

    def _parse_excel_file(self, excel_file, filename):
        """Parse Excel file and return rows"""
        if filename.endswith('.xlsx'):
            if openpyxl is None:
                return Response(
                    {"error": "openpyxl is required for .xlsx files", "hint": "Install with: pip install openpyxl"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            try:
                workbook = openpyxl.load_workbook(excel_file, data_only=True)
                sheet = workbook.active
                rows = list(sheet.iter_rows(values_only=True))
            except Exception as exc:
                return Response(
                    {"error": "Invalid Excel file", "details": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        elif filename.endswith('.xls'):
            if xlrd is None:
                return Response(
                    {"error": "xlrd is required for .xls files", "hint": "Install with: pip install xlrd"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            try:
                workbook = xlrd.open_workbook(file_contents=excel_file.read())
                sheet = workbook.sheet_by_index(0)
                rows = [sheet.row_values(row_index) for row_index in range(sheet.nrows)]
            except Exception as exc:
                return Response(
                    {"error": "Invalid Excel file", "details": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        else:
            return Response(
                {"error": "Only .xls and .xlsx files are supported"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        return rows

    def _normalize_header(self, header_row):
        """Normalize header row"""
        return [str(val).strip() if val is not None else '' for val in header_row]

    def _extract_cell_value(self, row, column_index):
        """Safely extract and clean cell value"""
        if column_index is None or column_index >= len(row):
            return None
        
        value = row[column_index]
        
        if value is None or value == '':
            return None
        
        return str(value).strip()

    def _process_rows(self, data_rows, column_mapping):
        """Process data rows and import leads"""
        imported_count = 0
        row_errors = []
        leads_to_create = []
        campaigns_to_process = {}

        # First pass: validate and prepare data
        for row_number, row in enumerate(data_rows, start=2):
            # Skip completely empty rows
            if not any(cell not in (None, '') for cell in row):
                continue

            row_data = {}
            
            # Extract required fields
            fullname = self._extract_cell_value(row, column_mapping.get('fullname'))
            phone_number = self._extract_cell_value(row, column_mapping.get('phone_number'))
            email = self._extract_cell_value(row, column_mapping.get('email'))
            
            # Extract optional fields
            status_value = self._extract_cell_value(row, column_mapping.get('status'))
            campaign_name = self._extract_cell_value(row, column_mapping.get('campaign'))
            
            # Build row data
            row_data['fullname'] = fullname or ''
            row_data['phone_number'] = phone_number or ''
            row_data['email'] = email or ''
            row_data['status'] = status_value.lower() if status_value else None
            
            # Validate using serializer
            serializer = LeadSerializer(data=row_data, partial=True)
            if not serializer.is_valid():
                row_errors.append({
                    'row': row_number,
                    'data': row_data,
                    'errors': serializer.errors
                })
                continue
            
            # Prepare lead for creation
            leads_to_create.append({
                'row_number': row_number,
                'data': serializer.validated_data,
                'campaign_name': campaign_name,
            })
            
            # Track campaigns
            if campaign_name:
                campaigns_to_process[campaign_name] = None

        # Create campaigns first
        for campaign_name in campaigns_to_process.keys():
            campaign = CampaignHandler.get_or_create_campaign(campaign_name)
            campaigns_to_process[campaign_name] = campaign

        # Bulk create leads in transaction
        if leads_to_create:
            with transaction.atomic():
                for lead_info in leads_to_create:
                    lead_data = lead_info['data']
                    campaign_name = lead_info['campaign_name']
                    
                    # Add campaign if exists
                    if campaign_name and campaigns_to_process.get(campaign_name):
                        lead_data['campaign'] = campaigns_to_process[campaign_name]
                    
                    lead = Lead.objects.create(**lead_data)
                    imported_count += 1

        # Prepare response
        response_data = {
            "success": True,
            "summary": {
                "total_rows_processed": len(data_rows),
                "imported": imported_count,
                "failed": len(row_errors),
            }
        }
        
        if row_errors:
            response_data["validation_errors"] = row_errors
            response_code = status.HTTP_207_MULTI_STATUS  # Partial success
        else:
            response_code = status.HTTP_201_CREATED if imported_count > 0 else status.HTTP_204_NO_CONTENT

        return Response(response_data, status=response_code)


class LeadStatusChoicesView(APIView):
    def get(self, request):
        choices = [
            {"key": key, "label": label}
            for key, label in Lead.STATUS_CHOICES
        ]
        return Response({"status_choices": choices}, status=status.HTTP_200_OK)

    def patch(self, request):
        permission_classes = [IsAdminOnly]
        if not request.user.is_authenticated or not (request.user.is_superuser or getattr(request.user, 'role', None) == 'blog_admin'):
            return Response(
                {"error": "Only admins can update status choices"},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_statuses = request.data.get('status_choices', [])
        if not isinstance(new_statuses, list) or not new_statuses:
            return Response(
                {"error": "status_choices must be a non-empty list of {key, label} objects"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for choice in new_statuses:
            if not isinstance(choice, dict) or 'key' not in choice or 'label' not in choice:
                return Response(
                    {"error": "Each status choice must have 'key' and 'label' fields"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        Lead.STATUS_CHOICES = [(choice['key'], choice['label']) for choice in new_statuses]

        return Response(
            {"message": "Status choices updated successfully", "status_choices": new_statuses},
            status=status.HTTP_200_OK,
        )

