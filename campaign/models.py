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

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name
