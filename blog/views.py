from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Blog
from .serializers import BlogSerializer, BlogCategorySerializer, TagSerializer
from .permissions import IsAdminOnly


def sync_blog_categories_from_courses():
    """Mirror course categories into blog categories by name."""
    from .models import BlogCategory

    try:
        from courses.models import Category as CourseCategory
    except Exception:
        return

    course_names = CourseCategory.objects.values_list("name", flat=True)
    for name in course_names:
        clean_name = (name or "").strip()
        if not clean_name:
            continue
        BlogCategory.objects.get_or_create(name=clean_name)


class BlogPagination(PageNumberPagination):
    page_size = 5


# ---------------- ADMIN BLOG CRUD ---------------- #

class AdminBlogListCreateView(APIView):
    permission_classes = [IsAdminOnly, IsAuthenticated]

    def get(self, request):
        search = request.GET.get("search")
        status_filter = request.GET.get("status")

        blogs = Blog.objects.filter(is_deleted=False).order_by("-created_at")

        if search:
            blogs = blogs.filter(
                Q(title__icontains=search) |
                Q(content__icontains=search)
            )

        if status_filter:
            blogs = blogs.filter(status=status_filter)

        paginator = BlogPagination()
        result_page = paginator.paginate_queryset(blogs, request)
        serializer = BlogSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = BlogSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(author=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminBlogMetaView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOnly]

    def get(self, request):
        from .models import BlogCategory, Tag

        sync_blog_categories_from_courses()

        categories = BlogCategory.objects.all().order_by("name")
        tags = Tag.objects.all().order_by("name")

        return Response(
            {
                "categories": BlogCategorySerializer(categories, many=True).data,
                "tags": TagSerializer(tags, many=True).data,
            }
        )


class AdminBlogCategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOnly]

    def get(self, request):
        from .models import BlogCategory

        sync_blog_categories_from_courses()

        categories = BlogCategory.objects.all().order_by("name")
        serializer = BlogCategorySerializer(categories, many=True)
        return Response(serializer.data)

    def post(self, request):
        from .models import BlogCategory

        raw_name = request.data.get("name") or ""
        name = " ".join(str(raw_name).split()).strip()
        if not name:
            return Response({"detail": "Category name is required."}, status=status.HTTP_400_BAD_REQUEST)
        if len(name) > 150:
            return Response({"detail": "Category name cannot exceed 150 characters."}, status=status.HTTP_400_BAD_REQUEST)

        existing = BlogCategory.objects.filter(name__iexact=name).first()
        if existing:
            serializer = BlogCategorySerializer(existing)
            return Response(
                {
                    "created": False,
                    "detail": "Category already exists.",
                    "category": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        serializer = BlogCategorySerializer(data={"name": name})
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "created": True,
                    "detail": "Category created successfully.",
                    "category": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminBlogDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOnly]

    def get(self, request, id):
        blog = get_object_or_404(Blog, id=id, is_deleted=False)
        serializer = BlogSerializer(blog)
        return Response(serializer.data)

    def put(self, request, id):
        blog = get_object_or_404(Blog, id=id, is_deleted=False)
        serializer = BlogSerializer(blog, data=request.data)  # Full update
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, id):
        blog = get_object_or_404(Blog, id=id, is_deleted=False)
        serializer = BlogSerializer(blog, data=request.data, partial=True) # Partial update
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        blog = get_object_or_404(Blog, id=id)
        blog.is_deleted = True
        blog.save()
        return Response({"message": "Blog soft deleted"}, status=status.HTTP_200_OK)


# ---------------- HOME PAGE APIs ---------------- #

from rest_framework.decorators import api_view, permission_classes

@api_view(['GET'])
@permission_classes([AllowAny])
def latest_blogs(request):
    """
    Returns the latest 3 published blogs. 
    Also triggers auto-publishing for scheduled blogs that are due.
    """
    from django.utils import timezone
    now = timezone.now()

    # 🔥 Auto-publish due blogs
    Blog.objects.filter(
        status="scheduled", 
        publish_at__lte=now, 
        is_deleted=False
    ).update(status="published")

    # Fetch latest 3 published blogs
    blogs = Blog.objects.filter(
        status='published', 
        is_deleted=False
    ).order_by('-publish_at')[:3]
    
    serializer = BlogSerializer(blogs, many=True)
    return Response(serializer.data)


# ---------------- PUBLIC APIs ---------------- #

class PublicBlogListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from django.utils import timezone
        now = timezone.now()
        
        # 🔥 Auto-publish due blogs
        Blog.objects.filter(
            status="scheduled",
            publish_at__lte=now,
            is_deleted=False
        ).update(status="published")
        
        blogs = Blog.objects.filter(
            is_deleted=False,
            status="published"
        ).order_by("-publish_at", "-created_at")

        serializer = BlogSerializer(blogs, many=True)
        return Response(serializer.data)


class PublicBlogDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        from django.utils import timezone
        now = timezone.now()
        
        # 🔥 Auto-publish this specific blog if it's due
        Blog.objects.filter(
            slug=slug,
            status="scheduled",
            publish_at__lte=now,
            is_deleted=False
        ).update(status="published")

        blog = get_object_or_404(
            Blog,
            slug=slug,
            is_deleted=False,
            status="published"
        )

        serializer = BlogSerializer(blog)
        return Response(serializer.data)