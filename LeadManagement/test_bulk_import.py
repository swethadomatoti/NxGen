"""
Test suite for Lead Bulk Import functionality

Run with: python manage.py test LeadManagement.tests.BulkImportTests
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from io import BytesIO
import openpyxl

from LeadManagement.models import Lead
from campaign.models import Campaign


class BulkImportTests(TestCase):
    """Test cases for bulk import functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create admin user
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='testpass123'
        )
        
        # Create campaign for testing
        self.campaign = Campaign.objects.create(
            name='Test Campaign',
            status='active',
            start_date='2026-05-01',
            end_date='2026-06-01'
        )

    def create_test_excel_file(self, rows):
        """
        Create a test Excel file with given rows
        First row is header, subsequent rows are data
        """
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        
        for row_data in rows:
            sheet.append(row_data)
        
        # Write to BytesIO
        file_obj = BytesIO()
        workbook.save(file_obj)
        file_obj.seek(0)
        
        return file_obj

    def test_basic_import_minimal_fields(self):
        """Test importing leads with minimal required fields"""
        self.client.force_authenticate(user=self.admin_user)
        
        excel_file = self.create_test_excel_file([
            ['Full Name', 'Phone', 'Email'],
            ['John Doe', '9876543210', 'john@example.com'],
            ['Jane Smith', '9123456789', 'jane@example.com'],
        ])
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': excel_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['summary']['imported'], 2)
        self.assertEqual(Lead.objects.count(), 2)

    def test_import_with_various_column_names(self):
        """Test that various column name variations work"""
        self.client.force_authenticate(user=self.admin_user)
        
        excel_file = self.create_test_excel_file([
            ['name', 'Mobile Number', 'E-mail'],  # Different column names
            ['John Doe', '9876543210', 'john@example.com'],
        ])
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': excel_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['summary']['imported'], 1)

    def test_import_with_status_field(self):
        """Test importing with optional status field"""
        self.client.force_authenticate(user=self.admin_user)
        
        excel_file = self.create_test_excel_file([
            ['Full Name', 'Phone', 'Email', 'Status'],
            ['John Doe', '9876543210', 'john@example.com', 'interested'],
            ['Jane Smith', '9123456789', 'jane@example.com', 'contacted'],
        ])
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': excel_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        lead1 = Lead.objects.get(fullname='John Doe')
        lead2 = Lead.objects.get(fullname='Jane Smith')
        
        self.assertEqual(lead1.status, 'interested')
        self.assertEqual(lead2.status, 'contacted')

    def test_import_with_campaign(self):
        """Test importing leads with campaign association"""
        self.client.force_authenticate(user=self.admin_user)
        
        excel_file = self.create_test_excel_file([
            ['Full Name', 'Phone', 'Email', 'Campaign'],
            ['John Doe', '9876543210', 'john@example.com', 'New Campaign'],
            ['Jane Smith', '9123456789', 'jane@example.com', 'New Campaign'],
        ])
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': excel_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check that campaign was created
        new_campaign = Campaign.objects.get(name='New Campaign')
        self.assertEqual(new_campaign.status, 'upcoming')
        
        # Check that leads are linked to campaign
        leads = Lead.objects.filter(campaign=new_campaign)
        self.assertEqual(leads.count(), 2)

    def test_import_with_existing_campaign(self):
        """Test importing leads to existing campaign"""
        self.client.force_authenticate(user=self.admin_user)
        
        existing_lead_count = Lead.objects.filter(campaign=self.campaign).count()
        
        excel_file = self.create_test_excel_file([
            ['Full Name', 'Phone', 'Email', 'Campaign'],
            ['John Doe', '9876543210', 'john@example.com', 'Test Campaign'],
        ])
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': excel_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Campaign should not be duplicated
        self.assertEqual(Campaign.objects.filter(name='Test Campaign').count(), 1)
        
        # Lead should be linked to existing campaign
        new_lead_count = Lead.objects.filter(campaign=self.campaign).count()
        self.assertEqual(new_lead_count, existing_lead_count + 1)

    def test_import_skips_empty_rows(self):
        """Test that empty rows are skipped"""
        self.client.force_authenticate(user=self.admin_user)
        
        excel_file = self.create_test_excel_file([
            ['Full Name', 'Phone', 'Email'],
            ['John Doe', '9876543210', 'john@example.com'],
            [None, None, None],  # Empty row
            ['Jane Smith', '9123456789', 'jane@example.com'],
        ])
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': excel_file},
            format='multipart'
        )
        
        # Only 2 leads should be imported (empty row skipped)
        self.assertEqual(response.data['summary']['imported'], 2)

    def test_import_continues_on_validation_error(self):
        """Test that import continues even if one row has validation error"""
        self.client.force_authenticate(user=self.admin_user)
        
        excel_file = self.create_test_excel_file([
            ['Full Name', 'Phone', 'Email'],
            ['John Doe', '9876543210', 'john@example.com'],
            ['', '9123456789', 'jane@example.com'],  # Missing fullname
            ['Bob Johnson', '9987654321', 'bob@example.com'],
        ])
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': excel_file},
            format='multipart'
        )
        
        # Should return 207 Multi-Status (partial success)
        self.assertEqual(response.status_code, status.HTTP_207_MULTI_STATUS)
        self.assertEqual(response.data['summary']['imported'], 2)
        self.assertEqual(response.data['summary']['failed'], 1)
        
        # Valid leads should still be imported
        self.assertEqual(Lead.objects.filter(fullname='John Doe').count(), 1)
        self.assertEqual(Lead.objects.filter(fullname='Bob Johnson').count(), 1)

    def test_import_invalid_email_format(self):
        """Test that invalid email format is caught"""
        self.client.force_authenticate(user=self.admin_user)
        
        excel_file = self.create_test_excel_file([
            ['Full Name', 'Phone', 'Email'],
            ['John Doe', '9876543210', 'invalid-email'],  # Invalid email
        ])
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': excel_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_207_MULTI_STATUS)
        self.assertEqual(response.data['summary']['failed'], 1)

    def test_import_missing_required_column(self):
        """Test that missing required column is caught at validation"""
        self.client.force_authenticate(user=self.admin_user)
        
        excel_file = self.create_test_excel_file([
            ['Full Name', 'Email'],  # Missing phone column
            ['John Doe', 'john@example.com'],
        ])
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': excel_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', response.data['missing_fields'])

    def test_import_no_file_provided(self):
        """Test that missing file is handled"""
        self.client.force_authenticate(user=self.admin_user)
        
        response = self.client.post('/api/lead/bulk-import/')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Excel file is required')

    def test_import_requires_authentication(self):
        """Test that unauthenticated users cannot import"""
        excel_file = self.create_test_excel_file([
            ['Full Name', 'Phone', 'Email'],
            ['John Doe', '9876543210', 'john@example.com'],
        ])
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': excel_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_case_insensitive_column_mapping(self):
        """Test that column names are case-insensitive"""
        self.client.force_authenticate(user=self.admin_user)
        
        excel_file = self.create_test_excel_file([
            ['FULL NAME', 'PHONE', 'EMAIL'],  # All uppercase
            ['John Doe', '9876543210', 'john@example.com'],
        ])
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': excel_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_space_insensitive_column_mapping(self):
        """Test that column names with different spaces work"""
        self.client.force_authenticate(user=self.admin_user)
        
        excel_file = self.create_test_excel_file([
            ['full  name', 'phone  number', 'email  address'],  # Extra spaces
            ['John Doe', '9876543210', 'john@example.com'],
        ])
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': excel_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_empty_excel_file(self):
        """Test that empty Excel file is rejected"""
        self.client.force_authenticate(user=self.admin_user)
        
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        
        file_obj = BytesIO()
        workbook.save(file_obj)
        file_obj.seek(0)
        
        response = self.client.post(
            '/api/lead/bulk-import/',
            {'file': file_obj},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Excel file is empty')
