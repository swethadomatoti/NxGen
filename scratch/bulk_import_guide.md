# 🎯 Lead Bulk Import Guide

## Overview
The bulk import endpoint allows you to import leads from Excel files (.xlsx/.xls) with flexible column mapping and automatic campaign association.

---

## 📋 API Endpoint

**POST** `/api/lead/bulk-import/`

### Authentication
- Required: Admin/Staff user
- Use Django REST Framework token authentication or session authentication

### File Format
- Accept `.xlsx` (Excel 2007+) or `.xls` (Excel 97-2003)
- Maximum file size: Depends on server configuration
- Supported libraries: `openpyxl` for .xlsx, `xlrd` for .xls

---

## 🧭 Column Mapping (Flexible)

The system automatically maps Excel columns to Lead fields using **case-insensitive** and **space-insensitive** matching.

### Supported Column Names

#### Full Name (REQUIRED)
- `fullname`
- `full_name`
- `full name`
- `name`
- `participant name`
- `student name`

#### Phone Number (REQUIRED)
- `phone_number`
- `phone`
- `mobile_number`
- `mobile`
- `mobile number`
- `contact`
- `phone_no`

#### Email (REQUIRED)
- `email`
- `email_address`
- `email address`
- `e-mail`
- `mail`

#### Status (OPTIONAL)
- `status`
- `lead status`
- `lead_status`
- Valid values: `interested`, `contacted`

#### Campaign (OPTIONAL)
- `campaign`
- `campaign_name`
- `campaign name`
- If campaign doesn't exist, it will be created automatically with status='upcoming'

---

## 📊 Example Excel Files

### Example 1: Minimal (Required Fields Only)
```
Full Name          | Phone      | Email
John Doe          | 9876543210 | john@example.com
Jane Smith        | 9123456789 | jane@example.com
```

### Example 2: With Status and Campaign
```
Full Name    | Phone      | Email               | Status    | Campaign
John Doe     | 9876543210 | john@example.com    | interested| Summer 2026
Jane Smith   | 9123456789 | jane@example.com    | contacted | Summer 2026
Bob Johnson  | 9987654321 | bob@example.com     | interested| Fall 2026
```

### Example 3: Various Column Names (All Work!)
```
name           | Mobile Number | E-mail          | lead status | campaign_name
John Doe       | 9876543210    | john@example.com| interested  | Summer 2026
Jane Smith     | 9123456789    | jane@example.com| contacted   | Summer 2026
Bob Johnson    | 9987654321    | bob@example.com | interested  | Fall 2026
```

---

## 🚀 Usage Examples

### Python (requests library)
```python
import requests

# Prepare file
with open('leads.xlsx', 'rb') as f:
    files = {'file': f}
    
    # API endpoint
    url = 'http://localhost:8000/api/lead/bulk-import/'
    
    # Headers with auth token
    headers = {'Authorization': 'Token YOUR_AUTH_TOKEN'}
    
    # POST request
    response = requests.post(url, files=files, headers=headers)
    
    print(response.json())
```

### cURL
```bash
curl -X POST http://localhost:8000/api/lead/bulk-import/ \
  -F "file=@leads.xlsx" \
  -H "Authorization: Token YOUR_AUTH_TOKEN"
```

### JavaScript (Fetch API)
```javascript
const file = document.getElementById('fileInput').files[0];
const formData = new FormData();
formData.append('file', file);

fetch('/api/lead/bulk-import/', {
  method: 'POST',
  headers: {
    'Authorization': 'Token YOUR_AUTH_TOKEN',
  },
  body: formData
})
.then(response => response.json())
.then(data => console.log(data));
```

---

## 📤 Response Format

### Success Response (All rows imported)
```json
{
  "success": true,
  "summary": {
    "total_rows_processed": 3,
    "imported": 3,
    "failed": 0
  }
}
```
Status: **201 Created**

### Partial Success (Some rows failed, but others imported)
```json
{
  "success": true,
  "summary": {
    "total_rows_processed": 5,
    "imported": 3,
    "failed": 2
  },
  "validation_errors": [
    {
      "row": 2,
      "data": {
        "fullname": "John Doe",
        "phone_number": "",
        "email": "john@example.com",
        "status": null
      },
      "errors": {
        "phone_number": ["This field may not be blank."]
      }
    },
    {
      "row": 4,
      "data": {
        "fullname": "",
        "phone_number": "9876543210",
        "email": "test@example.com",
        "status": null
      },
      "errors": {
        "fullname": ["This field may not be blank."]
      }
    }
  ]
}
```
Status: **207 Multi-Status**

### Empty Excel File
```json
{
  "error": "Excel file is empty"
}
```
Status: **400 Bad Request**

### Missing Required Columns
```json
{
  "error": "Excel file is missing required columns",
  "missing_fields": ["phone_number"],
  "hint": "Required columns: Full Name, Phone Number, Email (case-insensitive)"
}
```
Status: **400 Bad Request**

### Missing File
```json
{
  "error": "Excel file is required"
}
```
Status: **400 Bad Request**

### Invalid File Format
```json
{
  "error": "Only .xls and .xlsx files are supported"
}
```
Status: **400 Bad Request**

### Missing Library
```json
{
  "error": "openpyxl is required for .xlsx files",
  "hint": "Install with: pip install openpyxl"
}
```
Status: **500 Internal Server Error**

---

## ⚙️ Features

### ✅ Flexible Column Mapping
- Case-insensitive: "Full Name", "full name", "FULLNAME" all work
- Space-insensitive: "phone_number", "phone number", "phonenumber" all work
- Multiple aliases: Use any common variation of field names

### ✅ Smart Campaign Handling
- If campaign exists: Link lead to existing campaign
- If campaign doesn't exist: Automatically create with status='upcoming'
- If no campaign specified: Lead created without campaign association

### ✅ Row-wise Error Handling
- Doesn't stop on first error
- Collects all validation errors
- Imports valid rows, returns list of failed rows with reasons
- Transactions ensure atomicity

### ✅ Empty Row Skipping
- Automatically skips completely empty rows
- Won't waste time on blank entries

### ✅ Performance
- Uses Django transactions for atomicity
- Bulk operations where possible
- Efficient memory usage even with large files

### ✅ Validation
- Email format validation
- Status value validation (must be 'interested' or 'contacted')
- Required field validation
- Phone number presence check

---

## 🧪 Test Data (SQL)

If you want to test programmatically:

```sql
-- Create a campaign first
INSERT INTO campaign_campaign (name, status, start_date, end_date)
VALUES ('Test Campaign', 'upcoming', '2026-05-01', '2026-06-01');

-- Check imported leads
SELECT id, fullname, email, phone_number, status, campaign_id, created_at
FROM LeadManagement_lead
ORDER BY created_at DESC;
```

---

## 🐛 Troubleshooting

### Issue: "openpyxl is required"
**Solution:** Install the package
```bash
pip install openpyxl
# or
pip install -r requirements.txt
```

### Issue: "xlrd is required"
**Solution:** Install the package
```bash
pip install xlrd
# or
pip install -r requirements.txt
```

### Issue: "Excel file is missing required columns"
**Solution:** Ensure your Excel file has:
- A column for full name (Full Name, Name, Participant Name, etc.)
- A column for phone number (Phone, Mobile Number, Phone_Number, etc.)
- A column for email (Email, E-mail, Email Address, etc.)

### Issue: "403 Forbidden"
**Solution:** Only admin users can import leads. Ensure:
- User has admin/staff status
- Request includes valid authentication token
- User has permission `IsAdminOnly`

### Issue: Some rows imported, some failed
**Solution:** This is expected behavior. Review the `validation_errors` in the response:
- Check if required fields are present in failed rows
- Verify email format is valid
- Ensure phone numbers are in correct format
- Check if status values are correct ('interested' or 'contacted')

---

## 📈 Performance Notes

- **Small files (< 1000 rows):** ~1-2 seconds
- **Medium files (1000-10000 rows):** ~5-15 seconds
- **Large files (> 10000 rows):** Consider chunking

For very large imports, consider:
1. Splitting file into multiple smaller files
2. Using the Django management command (if created)
3. Implementing async task queue (Celery)

---

## 🔐 Security Notes

- Only authenticated admin users can import
- Input validation on all fields
- SQL injection prevention (using Django ORM)
- XSS prevention (JSON responses, no HTML rendering)
- CSRF protection (included in Django by default)
- Rate limiting recommended (configure in settings.py)

---

## 📝 Sample Test File Content

Create a file `test_import.xlsx` with this data:

| Full Name | Mobile Number | Email           | Status    | Campaign      |
|-----------|---------------|-----------------|-----------|---------------|
| John Doe  | 9876543210    | john@example.com| interested| Summer 2026   |
| Jane Smith| 9123456789    | jane@example.com| contacted | Summer 2026   |
| Bob Johnson| 9987654321   | bob@example.com | interested| Fall 2026     |
| Alice Brown| 9112233445   | alice@example.com| interested| Winter 2026   |
| Charlie Davis| 9998887776 | charlie@example.com| contacted| Spring 2026  |

Then import via:
```bash
curl -X POST http://localhost:8000/api/lead/bulk-import/ \
  -F "file=@test_import.xlsx" \
  -H "Authorization: Token YOUR_TOKEN"
```
