from django.db import models
from django.conf import settings
from .storage import AuthenticatedRawMediaCloudinaryStorage
from cloudinary_storage.storage import RawMediaCloudinaryStorage

User = settings.AUTH_USER_MODEL


class Category(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Course(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="courses"
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class CourseContent(models.Model):
    """Legacy model — kept for backward compatibility."""
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="contents"
    )
    title = models.CharField(max_length=300)
    description = models.TextField()

    def __str__(self):
        return self.title


class Module(models.Model):
    """
    A module belongs directly to a Course and is categorised
    into one of two sections: Training or Industry Readiness.
    Each module is created by a specific instructor.
    """
    SECTION_TYPES = (
        ("training", "Training"),
        ("industry_readiness", "Industry Readiness"),
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="modules"
    )
    # ✅ Track which instructor created this module
    created_by = models.ForeignKey(
        'instructors.Instructor',
        on_delete=models.CASCADE,
        related_name="created_modules",
        null=True,
        blank=True
    )
    section_type = models.CharField(
        max_length=50,
        choices=SECTION_TYPES,
        default="training"
    )
    title = models.CharField(max_length=255)
    order = models.IntegerField(default=0)
    
    # ✅ Audit timestamps
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        creator = f" (by {self.created_by.full_name})" if self.created_by else ""
        return f"[{self.get_section_type_display()}] {self.title}{creator}"


class Lesson(models.Model):
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="lessons"
    )
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    file = models.FileField(upload_to="lesson_files/", null=True, blank=True, storage=AuthenticatedRawMediaCloudinaryStorage())
    video_url = models.URLField(blank=True, null=True)
    resource_title = models.CharField(max_length=255, blank=True)
    resource_link = models.URLField(blank=True)
    
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class Assignment(models.Model):
    lesson = models.ForeignKey(
        Lesson, 
        on_delete=models.CASCADE, 
        related_name="assignments"
    )
    batch = models.ForeignKey(
        'Batch',
        on_delete=models.CASCADE,  # Changed to CASCADE to be stricter
        related_name="batch_assignments"
    )
    assignment_title = models.CharField(max_length=255)
    assignment_description = models.TextField(blank=True)
    assignment_due_date = models.DateTimeField(null=True, blank=True)
    
    file = models.FileField(upload_to="assignments/", null=True, blank=True, storage=AuthenticatedRawMediaCloudinaryStorage())

    instructor = models.ForeignKey(
        'instructors.Instructor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instructor_assignments",
        db_index=True
    )
    
    # Audit fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_assignments"
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_assignments"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.assignment_title} (Lesson: {self.lesson.title})"


class Submission(models.Model):
    STATUS_CHOICES = (
        ("submitted", "Submitted"),
        ("graded", "Graded"),
    )

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="submissions",
        null=True,
        blank=True
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="course_submissions"
    )
    text_answer = models.TextField(blank=True)
    file_upload = models.FileField(upload_to="submissions/", null=True, blank=True, storage=AuthenticatedRawMediaCloudinaryStorage())
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="submitted")
    score = models.PositiveIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_submissions",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('assignment', 'student')

    def __str__(self):
        assignment_title = self.assignment.title if self.assignment else "No Assignment"
        return f"{self.student.email} - {assignment_title}"


class Batch(models.Model):
    name = models.ForeignKey('campaign.Campaign', on_delete=models.CASCADE, related_name='batches', null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="batches"
    )
    instructor = models.ForeignKey(
        'instructors.Instructor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batches"
    )
    students = models.ManyToManyField(
        User,
        blank=True,
        related_name="enrolled_batches"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # ðŸ”¥ Live Class Fields (Instructor can start a class)
    live_link = models.URLField(blank=True, null=True, help_text="Teams or Zoom link for live class")
    is_live_class_active = models.BooleanField(default=False, help_text="Is the live class currently ongoing?")

    def __str__(self):
        return f"{self.name} - {self.course.title}"
