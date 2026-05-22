from rest_framework import serializers
from .models import Enrollment
from courses.models import Course
from LeadManagement.models import Lead


class EnrollmentSerializer(serializers.ModelSerializer):
    course_title = serializers.ReadOnlyField(source='course.title')
    course = serializers.SlugRelatedField(
        queryset=Course.objects.all(),
        slug_field='title',
        required=False
    )
    
    # Aliases for frontend convenience
    fullname = serializers.CharField(write_only=True, required=False)
    name = serializers.ReadOnlyField()
    phone = serializers.ReadOnlyField()
    lead_id = serializers.PrimaryKeyRelatedField(
        queryset=Lead.objects.all(),
        source='lead',
        required=False,
        write_only=True
    )
    
    # New field to show all courses the student is enrolled in
    all_enrolled_courses = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = '__all__'
        validators = []  # Disable default UniqueTogetherValidator to allow auto-population
        extra_kwargs = {
            'full_name': {'required': False, 'allow_null': True, 'allow_blank': True},
            'email': {'required': False, 'allow_null': True, 'allow_blank': True},
            'phone_number': {'required': False, 'allow_null': True, 'allow_blank': True},
            'lead': {'required': False},
        }

    def get_all_enrolled_courses(self, obj):
        if obj.email:
            enrollments = Enrollment.objects.filter(email=obj.email).select_related('course')
            return [
                {
                    "enrollment_id": e.id,
                    "course_id": e.course.id if e.course else None,
                    "course_title": e.course.title if e.course else None,
                    "status": e.status,
                    "fee_status": e.fee_status,
                }
                for e in enrollments
            ]
        return []

    def validate(self, attrs):
        # 1. Handle 'fullname' alias if provided
        if 'fullname' in attrs:
            attrs['full_name'] = attrs.pop('fullname')

        email = attrs.get('email')
        lead = attrs.get('lead')

        # 2. If lead is not provided, try to find it by email
        if not lead and email:
            lead = Lead.objects.filter(email=email).first()
            if lead:
                attrs['lead'] = lead

        # 3. Fetch lead details if lead is provided (explicitly or found via email)
        if lead:
            # Auto-populate enrollment fields from lead details
            if not attrs.get('full_name'):
                attrs['full_name'] = lead.fullname
            if not attrs.get('email'):
                attrs['email'] = lead.email
            if not attrs.get('phone_number'):
                attrs['phone_number'] = lead.phone_number

        # 4. Final validation to ensure required fields are present
        # Refresh local variables after potential auto-population
        email = attrs.get('email')
        full_name = attrs.get('full_name')
        phone_number = attrs.get('phone_number')

        errors = {}
        if not full_name:
            errors['full_name'] = "Full name is required."
        if not email:
            errors['email'] = "Email is required."
        if not phone_number:
            errors['phone_number'] = "Phone number is required."

        if errors:
            raise serializers.ValidationError(errors)

        # 5. Check for duplicate enrollment (same email and course)
        course = attrs.get('course')
        if email and course:
            exists = Enrollment.objects.filter(email=email, course=course).exclude(id=self.instance.id if self.instance else None).exists()
            if exists:
                raise serializers.ValidationError("This email is already enrolled in this course.")

        return attrs

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Replace course ID with course title
        if instance.course:
            ret['course'] = instance.course.title
        return ret
