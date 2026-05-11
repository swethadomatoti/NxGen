from rest_framework import serializers

from .models import Lead


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ['id', 'fullname', 'email', 'phone_number', 'status', 'campaign', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_status(self, value):
        if value in (None, ''):
            return None

        allowed_statuses = [choice[0] for choice in Lead.STATUS_CHOICES]
        if value not in allowed_statuses:
            raise serializers.ValidationError(
                f"Status must be one of: {', '.join(allowed_statuses)}."
            )

        return value

    def validate(self, data):
        # For full updates (PUT), require all fields
        if not self.partial:
            if not data.get('fullname'):
                raise serializers.ValidationError({'fullname': 'Full name is required.'})
            if not data.get('email'):
                raise serializers.ValidationError({'email': 'Email is required.'})
            if not data.get('phone_number'):
                raise serializers.ValidationError({'phone_number': 'Phone number is required.'})
        else:
            # For partial updates (PATCH), only validate fields being updated
            if 'fullname' in data and not data.get('fullname'):
                raise serializers.ValidationError({'fullname': 'Full name cannot be empty.'})
            if 'email' in data and not data.get('email'):
                raise serializers.ValidationError({'email': 'Email cannot be empty.'})
            if 'phone_number' in data and not data.get('phone_number'):
                raise serializers.ValidationError({'phone_number': 'Phone number cannot be empty.'})

        return data
