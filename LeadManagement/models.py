from django.db import models
from django.db.models import CASCADE


class Lead(models.Model):

    STATUS_CHOICES = [
        ('interested', 'interested'),
        ('contacted', 'contacted'),
    ]

    fullname = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=32)
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        blank=True,
        null=True,
    )
    campaign = models.ForeignKey(
        'campaign.Campaign',
        on_delete=CASCADE,
        related_name='leads',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.fullname} <{self.email}>"
