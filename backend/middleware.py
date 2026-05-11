"""
Custom middleware to handle trailing slashes for all HTTP methods.
By default, Django only redirects GET requests. This middleware handles all methods.
"""
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponsePermanentRedirect, HttpResponse


class TrailingSlashMiddleware(MiddlewareMixin):
    """
    Handles trailing slash redirects for all HTTP methods.
    Redirects /path to /path/ for API endpoints.
    Uses 307 status code to preserve HTTP method during redirect.
    """
    
    def process_request(self, request):
        """
        Add trailing slash if missing (all HTTP methods).
        """
        # Don't process admin or static files
        if request.path.startswith('/admin') or request.path.startswith('/static'):
            return None
        
        path = request.path
        
        # If path doesn't end with slash and is an API endpoint
        if not path.endswith('/') and path.startswith('/api/'):
            # Check if it has a file extension (skip those)
            if not any(path.endswith(ext) for ext in ['.json', '.png', '.jpg', '.css', '.js']):
                new_path = path + '/'
                
                # Preserve query string
                if request.META.get('QUERY_STRING'):
                    new_path = new_path + '?' + request.META.get('QUERY_STRING')
                
                # Use 307 Temporary Redirect to preserve HTTP method (POST, PUT, PATCH stay same)
                response = HttpResponse(status=307)
                response['Location'] = new_path
                return response
        
        return None
