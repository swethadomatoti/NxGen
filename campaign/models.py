from django.db import models


class Campaign(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('upcoming', 'Upcoming'),
        ('completed', 'Completed'),
        ('inactive', 'Inactive'),
    ]

    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='upcoming',
    )
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True, null=True)

    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='campaigns',
        null=True,
        blank=True,
        help_text="The course associated with this campaign. If selected, a batch will be auto-created."
    )

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Automatically create a Batch when a new Campaign is created with an associated Course
        if is_new and self.course:
            from courses.models import Batch
            Batch.objects.create(
                name=self,
                course=self.course,
                description=f"Auto-generated batch for campaign: {self.name}"
            )
