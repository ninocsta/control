import mimetypes

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import HttpResponse
from django.views.static import serve

# Tipos que o navegador pode abrir inline; o resto sai como download.
INLINE_MEDIA_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf'}


def health(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return HttpResponse('ok', content_type='text/plain')


@login_required
def media(request, path):
    """Media nunca pública (contratos): só com login."""
    response = serve(request, path, document_root=settings.MEDIA_ROOT)  # safe_join barra ../
    response['X-Content-Type-Options'] = 'nosniff'
    if mimetypes.guess_type(path)[0] not in INLINE_MEDIA_TYPES:
        response['Content-Disposition'] = 'attachment'
    return response
