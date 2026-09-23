import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

MEDIA = tempfile.mkdtemp()
(Path(MEDIA) / 'c.pdf').write_bytes(b'%PDF')
(Path(MEDIA) / 'x.html').write_bytes(b'<script>')


@override_settings(MEDIA_ROOT=MEDIA)
class MediaHealthTests(TestCase):
    def test_health(self):
        self.assertEqual(self.client.get('/health/').status_code, 200)

    def test_media_exige_login(self):
        self.assertEqual(self.client.get('/media/c.pdf').status_code, 302)
        self.client.force_login(User.objects.create_user('u'))
        r = self.client.get('/media/c.pdf')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['X-Content-Type-Options'], 'nosniff')
        self.assertFalse(r.get('Content-Disposition', '').startswith('attachment'))
        self.assertEqual(self.client.get('/media/x.html')['Content-Disposition'], 'attachment')
