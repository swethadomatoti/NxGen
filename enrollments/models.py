from django.db import models
from courses.models import Course


class Enrollment(models.Model):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    COURSE_TYPE_CHOICES = (
        ('Training', 'training'),
        ('Industry Readiness', 'industry readiness'),
    )

    MODE_CHOICES = (
        ('Online', 'online'),
        ('Offline', 'offline'),
    )

    TIMING_CHOICES = (
        ('Morning', 'morning'),
        ('Afternoon', 'afternoon'),
        ('Evening', 'evening'),
    )

    EXPERIENCE_CHOICES = (
        ('Beginner', 'beginner'),
        ('Intermediate', 'intermediate'),
        ('Experienced', 'experienced'),
    )

    CURRENT_STATUS_CHOICES = (
        ('Student', 'student'),
        ('Working', 'working'),
        ('Job Seeker', 'job_seeker'),
    )


    # 🔥 BASIC INFO
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=15)

    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    # 🔥 NEW FIELDS FROM UI
    course_type = models.CharField(max_length=20, choices=COURSE_TYPE_CHOICES)
    qualification = models.CharField(max_length=100)
    current_status = models.CharField(max_length=50, choices=CURRENT_STATUS_CHOICES)

    organization = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )  # college/company

    preferred_mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    preferred_timing = models.CharField(max_length=50, choices=TIMING_CHOICES)

    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_CHOICES)

    terms_accepted = models.BooleanField(default=False)

    # 🔥 PAYMENT
    payment_status = models.CharField(max_length=20, default="pending")
    razorpay_order_id = models.CharField(max_length=200, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=200, blank=True, null=True)

    # 🔥 STATUS
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')                                                             
    is_active = models.BooleanField(default=False)

    # 🔥 NEW FIELDS
    enrollment_date = models.DateField(null=True, blank=True)
    fee_status = models.CharField(
        max_length=20, 
        choices=[
            ('Pending', 'Pending'),
            ('Paid', 'Paid'),
            ('Partially Paid', 'Partially Paid'),
        ],
        default='Pending'
    )
    
    # Support for lead linking if needed
    lead = models.ForeignKey(
        'LeadManagement.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enrolled_records'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('email', 'course')

    def __str__(self):
        return f"{self.name} - {self.course.title}"

    @property
    def full_name(self):
        return self.name

    @property
    def phone_number(self):
        return self.phone