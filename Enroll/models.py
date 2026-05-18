from django.db import models


class Enrollment(models.Model):
    COURSE_TYPE_CHOICES = [
        ('Training', 'Training'),
        ('Industry Readiness', 'Industry Readiness'),
    ]

    CURRENT_STATUS_CHOICES = [
        ('Student', 'Student'),
        ('Working Professional', 'Working Professional'),
        ('Job Seeker', 'Job Seeker'),
    ]

    MODE_CHOICES = [
        ('Online', 'Online'),
        ('Offline', 'Offline'),
    ]

    TIMING_CHOICES = [
        ('Morning', 'Morning'),
        ('Afternoon', 'Afternoon'),
        ('Evening', 'Evening'),
    ]

    EXPERIENCE_CHOICES = [
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
    ]

    FEE_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Partially Paid', 'Partially Paid'),
    ]

    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15)
    
    course = models.ForeignKey(
        'courses.Course', 
        on_delete=models.CASCADE, 
        related_name='enroll_app_enrollments'
    )
    
    course_type = models.CharField(max_length=50, choices=COURSE_TYPE_CHOICES, default='Training')
    qualification = models.CharField(max_length=255)
    current_status = models.CharField(max_length=50, choices=CURRENT_STATUS_CHOICES)
    organization = models.CharField(max_length=255, blank=True, null=True)  # College / Company Name
    
    preferred_mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    preferred_batch_timing = models.CharField(max_length=50, choices=TIMING_CHOICES)
    
    experience_level = models.CharField(max_length=50, choices=EXPERIENCE_CHOICES)
    fee_status = models.CharField(max_length=20, choices=FEE_STATUS_CHOICES, default='Pending')
    
    enrollment_date = models.DateField()
    agreed_to_terms = models.BooleanField(default=False)
    
    # 🔥 Fields to support existing frontend payload
    lead = models.ForeignKey(
        'LeadManagement.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='new_enrollments'
    )
    notes = models.TextField(blank=True, null=True)
    
    # Support for enrollments app logic
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=False)
    
    # Razorpay fields
    payment_status = models.CharField(max_length=20, default="pending")
    razorpay_order_id = models.CharField(max_length=200, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def name(self):
        return self.full_name

    @property
    def phone(self):
        return self.phone_number

    @property
    def preferred_timing(self):
        return self.preferred_batch_timing

    class Meta:
        ordering = ['-created_at']
        unique_together = ('email', 'course')

    def __str__(self):
        return f"{self.full_name} - {self.course.title}"

# --- Signals to sync with enrollments app ---
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Enrollment)
def sync_to_enrollments_app(sender, instance, **kwargs):
    """
    Automatically create or update a record in the enrollments app
    when an Enrollment in the Enroll app is marked as Paid or Partially Paid.
    """
    if instance.fee_status in ['Paid', 'Partially Paid']:
        from enrollments.models import Enrollment as EnrolledRecord
        
        # Try to find existing record by email and course
        enrolled_record, created = EnrolledRecord.objects.get_or_create(
            email=instance.email,
            course=instance.course,
            defaults={
                'name': instance.full_name,
                'phone': instance.phone_number,
                'course_type': instance.course_type,
                'qualification': instance.qualification,
                'current_status': instance.current_status,
                'organization': instance.organization,
                'preferred_mode': instance.preferred_mode,
                'preferred_timing': instance.preferred_batch_timing,
                'experience_level': instance.experience_level,
                'enrollment_date': instance.enrollment_date,
                'fee_status': instance.fee_status,
                'lead': instance.lead,
            }
        )
        
        if not created:
            # Update existing record with latest details from Enroll app
            enrolled_record.name = instance.full_name
            enrolled_record.phone = instance.phone_number
            enrolled_record.course_type = instance.course_type
            enrolled_record.qualification = instance.qualification
            enrolled_record.current_status = instance.current_status
            enrolled_record.organization = instance.organization
            enrolled_record.preferred_mode = instance.preferred_mode
            enrolled_record.preferred_timing = instance.preferred_batch_timing
            enrolled_record.experience_level = instance.experience_level
            enrolled_record.enrollment_date = instance.enrollment_date
            enrolled_record.fee_status = instance.fee_status
            enrolled_record.lead = instance.lead
            enrolled_record.save()
