from rest_framework import serializers
from django.core.exceptions import ObjectDoesNotExist

from courses.models import Course
from .models import Campaign


class CourseSlugOrIdRelatedField(serializers.SlugRelatedField):
    def to_internal_value(self, data):
        try:
            int_val = int(data)
            return self.get_queryset().get(pk=int_val)
        except (ValueError, TypeError):
            pass
        except ObjectDoesNotExist:
            raise serializers.ValidationError(f"Course with id={data} does not exist.")
            
        return super().to_internal_value(data)


class CampaignSerializer(serializers.ModelSerializer):
    course = CourseSlugOrIdRelatedField(
        queryset=Course.objects.all(),
        slug_field='title',
        allow_null=True,
        required=False
    )

    class Meta:
        model = Campaign
        fields = ['id', 'name', 'status', 'start_date', 'end_date', 'description', 'course']
        read_only_fields = ['id']

    def validate(self, data):
        start_date = data.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = data.get('end_date', getattr(self.instance, 'end_date', None))

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'End date must be on or after start date.'
            })

        return data
