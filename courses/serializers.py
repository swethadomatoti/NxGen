from rest_framework import serializers
from django.db.models import Q
from .models import Category, Course, CourseContent, Module, Lesson, Assignment, Submission, Batch
from .storage import get_signed_url


# ─────────────────────────────────────────────
# LESSON
# ─────────────────────────────────────────────
class AssignmentSerializer(serializers.ModelSerializer):
    batch = serializers.PrimaryKeyRelatedField(
        queryset=Batch.objects.all(),
        required=True,
        allow_null=False,
        help_text="Batch is mandatory to ensure students receive notification emails."
    )

    instructor_details = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = "__all__"
        read_only_fields = ('instructor', 'created_by', 'updated_by')

    def get_instructor_details(self, obj):
        if obj.instructor:
            return {
                "id": obj.instructor.id,
                "name": obj.instructor.full_name,
                "email": obj.instructor.email
            }
        return None

    def validate(self, attrs):
        request = self.context.get('request')
        if not request:
            return attrs
            
        user = request.user
        batch = attrs.get('batch')

        # ⚠️ Prevent assignment creation if batch.instructor is NULL
        if batch and not batch.instructor:
            raise serializers.ValidationError({
                "batch": "Cannot create assignment. This batch has no instructor assigned."
            })

        # 🔐 Role-based instructor assignment logic
        from accounts.models import User
        
        # Check if user is Admin (role constant or superuser)
        is_admin = getattr(user, 'role', '') == User.ADMIN or user.is_superuser
        is_instructor = getattr(user, 'role', '') == User.INSTRUCTOR

        if is_admin:
            # Admin Flow: assignment.instructor = batch.instructor
            attrs['instructor'] = batch.instructor
            # If instructor was manually sent, it's ignored/overridden because 'instructor' is in read_only_fields
            # but we explicitly set it in attrs here.
        elif is_instructor:
            if not hasattr(user, 'instructor'):
                raise serializers.ValidationError("Instructor profile not found for this user.")
            
            # ⚠️ Instructor cannot assign different instructor manually
            # System sets field automatically:
            attrs['instructor'] = user.instructor
            
            # ⚠️ Instructor cannot access other instructors' assignments / batches
            if batch.instructor != user.instructor:
                raise serializers.ValidationError({
                    "batch": "You can only assign assignments to your own batches."
                })
        
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['created_by'] = user
        validated_data['updated_by'] = user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user = self.context['request'].user
        validated_data['updated_by'] = user
        
        # 🔄 Assignment Update Logic: If batch is changed by Admin, update instructor
        from accounts.models import User
        is_admin = getattr(user, 'role', '') == User.ADMIN or user.is_superuser
        
        if is_admin and 'batch' in validated_data:
            validated_data['instructor'] = validated_data['batch'].instructor
            
        return super().update(instance, validated_data)


class LessonSerializer(serializers.ModelSerializer):
    assignments = AssignmentSerializer(many=True, read_only=True)

    def validate_file(self, value):
        if value and value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("max file size is 10MB")
        return value

    def to_internal_value(self, data):
        data = data.copy()

        from django.core.files.base import File
        raw_file = data.get('file', None)
        if raw_file is not None and not isinstance(raw_file, File):
            data.pop('file', None)
            
        return super().to_internal_value(data)

    class Meta:
        model = Lesson
        fields = "__all__"


# ─────────────────────────────────────────────
# MODULE  (nested lessons — read only)
# ─────────────────────────────────────────────
class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")


# ─────────────────────────────────────────────
# MODULE  (write — no nested lessons)
# ─────────────────────────────────────────────
class ModuleWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")


# ─────────────────────────────────────────────
# COURSE CONTENT  (full structured display)
# Returns course with separated modules for
# training and industry_readiness
# ─────────────────────────────────────────────
class CourseContentDisplaySerializer(serializers.ModelSerializer):
    """
    Full read-only representation of a course's content:
      {
         "id": 1,
         ...
         "training_modules": [...],
         "industry_readiness_modules": [...]
      }
    """
    training_modules = serializers.SerializerMethodField()
    industry_readiness_modules = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "title", "description", "price",
            "category",
            "training_modules", "industry_readiness_modules",
        ]

    def get_training_modules(self, course):
        request = self.context.get("request")
        modules = course.modules.filter(section_type="training")

        if request and request.user.is_authenticated and getattr(request.user, "role", "") == "student":
            from .models import Batch
            student_batches = Batch.objects.filter(
                students=request.user,
                course=course,
                is_active=True,
            )
            instructor_ids = list(
                student_batches.exclude(instructor__isnull=True).values_list("instructor_id", flat=True)
            )
            if instructor_ids:
                modules = modules.filter(
                    Q(created_by_id__in=instructor_ids) | Q(created_by__isnull=True)
                )

        modules = modules.order_by("order")
        return ModuleSerializer(modules, many=True).data

    def get_industry_readiness_modules(self, course):
        request = self.context.get("request")
        modules = course.modules.filter(section_type="industry_readiness")

        if request and request.user.is_authenticated and getattr(request.user, "role", "") == "student":
            from .models import Batch
            student_batches = Batch.objects.filter(
                students=request.user,
                course=course,
                is_active=True,
            )
            instructor_ids = list(
                student_batches.exclude(instructor__isnull=True).values_list("instructor_id", flat=True)
            )
            if instructor_ids:
                modules = modules.filter(
                    Q(created_by_id__in=instructor_ids) | Q(created_by__isnull=True)
                )

        modules = modules.order_by("order")
        return ModuleSerializer(modules, many=True).data


# ─────────────────────────────────────────────
# COURSE CONTENT MODEL (legacy — kept)
# ─────────────────────────────────────────────
class CourseContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseContent
        fields = "__all__"


# ─────────────────────────────────────────────
# COURSE
# ─────────────────────────────────────────────
class CourseSerializer(serializers.ModelSerializer):
    contents = CourseContentSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = "__all__"


# ─────────────────────────────────────────────
# CATEGORY
# ─────────────────────────────────────────────
class CategorySerializer(serializers.ModelSerializer):
    courses = CourseSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = "__all__"


# ─────────────────────────────────────────────
# SUBMISSION
# ─────────────────────────────────────────────
class SubmissionSerializer(serializers.ModelSerializer):
    file_upload = serializers.FileField(
        required=True,
        allow_null=False,
        write_only=True,
        error_messages={'required': 'Assignment file is mandatory.', 'null': 'Assignment file is mandatory.'}
    )
    signed_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Submission
        fields = "__all__"
        extra_kwargs = {
            'file_upload': {'write_only': True}
        }

    def get_signed_url(self, obj):
        if obj.file_upload:
            try:
                return get_signed_url(obj.file_upload.name)
            except Exception:
                return None
        return None

    def validate_file_upload(self, value):
        if not value:
            raise serializers.ValidationError("Assignment file is mandatory.")
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("max file size is 10MB")
        return value


# ─────────────────────────────────────────────
# BATCH
# ─────────────────────────────────────────────
class BatchSerializer(serializers.ModelSerializer):
    students_detail = serializers.SerializerMethodField()
    course_title = serializers.ReadOnlyField(source='course.title')

    class Meta:
        model = Batch
        fields = "__all__"

    def get_students_detail(self, obj):
        return [
            {
                "id": s.id,
                "name": f"{s.first_name} {s.last_name}".strip() or s.email,
                "email": s.email,
            }
            for s in obj.students.all()
        ]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance and instance.instructor_id:
            if "instructor" in attrs and attrs["instructor"] != instance.instructor:
                raise serializers.ValidationError({
                    "instructor": "Instructor cannot be changed after the batch is assigned."
                })
        return attrs