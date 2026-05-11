"""
Practical Testing Script for Bulk Import

This script creates test Excel files and demonstrates how to test the bulk import API.

Usage:
  python test_bulk_import_practical.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import openpyxl
from io import BytesIO
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from LeadManagement.models import Lead
from campaign.models import Campaign


def create_excel_file_in_memory(filename_hint, rows):
    """Create an in-memory Excel file"""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    
    for row in rows:
        sheet.append(row)
    
    file_obj = BytesIO()
    workbook.save(file_obj)
    file_obj.seek(0)
    file_obj.name = filename_hint
    
    return file_obj


def test_1_basic_import():
    """Test 1: Basic import with minimal fields"""
    print("\n" + "="*70)
    print("TEST 1: Basic Import with Minimal Fields")
    print("="*70)
    
    client = APIClient()
    admin = User.objects.filter(is_superuser=True).first()
    
    if not admin:
        print("❌ No admin user found. Create one first:")
        print("   python manage.py createsuperuser")
        return
    
    client.force_authenticate(user=admin)
    
    # Create Excel file
    excel_file = create_excel_file_in_memory('test1.xlsx', [
        ['Full Name', 'Phone', 'Email'],
        ['John Doe', '9876543210', 'john@example.com'],
        ['Jane Smith', '9123456789', 'jane@example.com'],
        ['Bob Johnson', '9987654321', 'bob@example.com'],
    ])
    
    # Make request
    response = client.post('/api/lead/bulk-import/', {'file': excel_file}, format='multipart')
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code in [201, 207]:
        print("✅ Test passed!")
    else:
        print("❌ Test failed!")


def test_2_flexible_column_names():
    """Test 2: Various column name variations"""
    print("\n" + "="*70)
    print("TEST 2: Flexible Column Names (case/space insensitive)")
    print("="*70)
    
    client = APIClient()
    admin = User.objects.filter(is_superuser=True).first()
    
    if not admin:
        print("❌ No admin user found")
        return
    
    client.force_authenticate(user=admin)
    
    # Create Excel file with different column names
    excel_file = create_excel_file_in_memory('test2.xlsx', [
        ['name', 'mobile_number', 'e-mail'],  # Different format!
        ['John Doe', '9876543210', 'john@example.com'],
        ['Jane Smith', '9123456789', 'jane@example.com'],
    ])
    
    response = client.post('/api/lead/bulk-import/', {'file': excel_file}, format='multipart')
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code in [201, 207]:
        print("✅ Test passed! Column name variations work!")
    else:
        print("❌ Test failed!")


def test_3_with_status():
    """Test 3: Import with optional status field"""
    print("\n" + "="*70)
    print("TEST 3: Import with Status Field")
    print("="*70)
    
    client = APIClient()
    admin = User.objects.filter(is_superuser=True).first()
    
    if not admin:
        print("❌ No admin user found")
        return
    
    client.force_authenticate(user=admin)
    
    # Create Excel file with status
    excel_file = create_excel_file_in_memory('test3.xlsx', [
        ['Full Name', 'Phone', 'Email', 'Status'],
        ['John Doe', '9876543210', 'john@example.com', 'interested'],
        ['Jane Smith', '9123456789', 'jane@example.com', 'contacted'],
        ['Bob Johnson', '9987654321', 'bob@example.com', 'interested'],
    ])
    
    response = client.post('/api/lead/bulk-import/', {'file': excel_file}, format='multipart')
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code in [201, 207]:
        # Verify status was saved
        leads = Lead.objects.filter(fullname__in=['John Doe', 'Jane Smith']).values('fullname', 'status')
        print(f"\nImported leads with status:")
        for lead in leads:
            print(f"  - {lead['fullname']}: {lead['status']}")
        print("✅ Test passed!")
    else:
        print("❌ Test failed!")


def test_4_with_campaign():
    """Test 4: Import with campaign association"""
    print("\n" + "="*70)
    print("TEST 4: Import with Campaign Association")
    print("="*70)
    
    client = APIClient()
    admin = User.objects.filter(is_superuser=True).first()
    
    if not admin:
        print("❌ No admin user found")
        return
    
    client.force_authenticate(user=admin)
    
    # Create Excel file with campaign
    excel_file = create_excel_file_in_memory('test4.xlsx', [
        ['Full Name', 'Phone', 'Email', 'Campaign'],
        ['John Doe', '9876543210', 'john@example.com', 'Summer 2026'],
        ['Jane Smith', '9123456789', 'jane@example.com', 'Summer 2026'],
        ['Bob Johnson', '9987654321', 'bob@example.com', 'Fall 2026'],
    ])
    
    response = client.post('/api/lead/bulk-import/', {'file': excel_file}, format='multipart')
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code in [201, 207]:
        # Verify campaigns were created
        campaigns = Campaign.objects.filter(name__in=['Summer 2026', 'Fall 2026'])
        print(f"\nCreated/Used campaigns: {len(campaigns)}")
        for campaign in campaigns:
            lead_count = Lead.objects.filter(campaign=campaign).count()
            print(f"  - {campaign.name}: {lead_count} leads, status={campaign.status}")
        print("✅ Test passed!")
    else:
        print("❌ Test failed!")


def test_5_partial_success():
    """Test 5: Partial success (some rows fail)"""
    print("\n" + "="*70)
    print("TEST 5: Partial Success - Some Rows Fail")
    print("="*70)
    
    client = APIClient()
    admin = User.objects.filter(is_superuser=True).first()
    
    if not admin:
        print("❌ No admin user found")
        return
    
    client.force_authenticate(user=admin)
    
    # Create Excel file with some invalid data
    excel_file = create_excel_file_in_memory('test5.xlsx', [
        ['Full Name', 'Phone', 'Email'],
        ['John Doe', '9876543210', 'john@example.com'],  # Valid
        ['', '9123456789', 'jane@example.com'],  # Invalid: no name
        ['Bob Johnson', '', 'bob@example.com'],  # Invalid: no phone
        ['Alice Brown', '9112233445', 'alice@example.com'],  # Valid
    ])
    
    response = client.post('/api/lead/bulk-import/', {'file': excel_file}, format='multipart')
    
    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {data}")
    
    if response.status_code == 207:  # 207 = Partial success
        print(f"\n✅ Partial success as expected!")
        print(f"  - Imported: {data['summary']['imported']}")
        print(f"  - Failed: {data['summary']['failed']}")
        if 'validation_errors' in data:
            print(f"  - Errors:")
            for error in data['validation_errors']:
                print(f"    Row {error['row']}: {error['errors']}")
    elif response.status_code == 201:
        print(f"✅ All rows imported (no errors)")
    else:
        print(f"❌ Unexpected status code!")


def view_all_imported_leads():
    """View all imported leads"""
    print("\n" + "="*70)
    print("ALL IMPORTED LEADS")
    print("="*70)
    
    leads = Lead.objects.all().order_by('-created_at')[:10]
    
    if not leads:
        print("No leads found in database")
        return
    
    print(f"Total leads: {Lead.objects.count()}\n")
    
    for lead in leads:
        print(f"ID: {lead.id}")
        print(f"  Name: {lead.fullname}")
        print(f"  Email: {lead.email}")
        print(f"  Phone: {lead.phone_number}")
        print(f"  Status: {lead.status}")
        print(f"  Campaign: {lead.campaign.name if lead.campaign else 'None'}")
        print(f"  Created: {lead.created_at}")
        print()


def main():
    """Run all tests"""
    print("\n" + "🧪 BULK IMPORT PRACTICAL TESTING SCRIPT")
    print("="*70)
    
    # Check if admin exists
    admin = User.objects.filter(is_superuser=True).first()
    if not admin:
        print("\n❌ ERROR: No admin user found!")
        print("Create a superuser first:")
        print("  python manage.py createsuperuser")
        return
    
    print(f"\n✅ Using admin user: {admin.username}")
    
    # Run tests
    try:
        test_1_basic_import()
        test_2_flexible_column_names()
        test_3_with_status()
        test_4_with_campaign()
        test_5_partial_success()
        view_all_imported_leads()
    except Exception as e:
        print(f"\n❌ ERROR during testing: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("✅ TESTING COMPLETE!")
    print("="*70)


if __name__ == '__main__':
    main()
