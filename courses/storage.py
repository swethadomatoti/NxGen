import cloudinary.utils
from cloudinary_storage.storage import MediaCloudinaryStorage, RawMediaCloudinaryStorage

class AuthenticatedMediaCloudinaryStorage(MediaCloudinaryStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'authenticated'

class AuthenticatedRawMediaCloudinaryStorage(RawMediaCloudinaryStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'authenticated'

from cloudinary.exceptions import NotFound
import cloudinary.api

def get_signed_url(public_id, resource_type=None):
    """
    Generates a signed URL for an authenticated Cloudinary resource.
    Automatically fetches resource type and handles legacy 'upload' types.
    """
    resource = None
    
    # Query Cloudinary directly to know exactly how it was stored
    for resource_type_candidate in ['raw', 'image', 'video']:
        if resource:
            break
        for delivery_type_candidate in ['authenticated', 'upload']:
            try:
                resource = cloudinary.api.resource(
                    public_id,
                    resource_type=resource_type_candidate,
                    type=delivery_type_candidate,
                )
                break
            except NotFound:
                continue

    if resource:
        r_type = resource.get('resource_type', 'raw')
        delivery_type = resource.get('type', 'upload')
        resource_format = resource.get('format')
        
        # Public ('upload') files do not require signing
        if delivery_type == 'upload':
            return resource.get('secure_url')

        # Build signed URL for authenticated files
        url_kwargs = {
            'resource_type': r_type,
            'type': 'authenticated',
            'sign_url': True,
        }

        if resource_format:
            url_kwargs['format'] = resource_format

        if r_type == 'raw':
            url_kwargs['flags'] = 'attachment:false'

        url, _ = cloudinary.utils.cloudinary_url(public_id, **url_kwargs)
        return url

    # Fallback to local guessing if Cloudinary API check didn't find the resource
    if not resource_type:
        ext = public_id.split('.')[-1].lower() if '.' in public_id else ''
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff']:
            resource_type = 'image'
        elif ext in ['mp4', 'mov', 'avi', 'mkv', 'webm']:
            resource_type = 'video'
        else:
            resource_type = 'raw'

    url_kwargs = {
        'resource_type': resource_type,
        'type': 'authenticated',
        'sign_url': True,
    }

    if resource_type == 'raw':
        url_kwargs['flags'] = 'attachment:false'
        ext = public_id.split('.')[-1].lower() if '.' in public_id else ''
        if ext in ['pdf', 'docx', 'xlsx', 'csv', 'txt', 'zip']:
            url_kwargs['format'] = ext

    url, options = cloudinary.utils.cloudinary_url(public_id, **url_kwargs)
    return url
