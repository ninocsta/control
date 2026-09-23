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
        self.assertEqual(r['Cache-Control'], 'private')
        self.assertFalse(r.get('Content-Disposition', '').startswith('attachment'))
        self.assertEqual(self.client.get('/media/x.html')['Content-Disposition'], 'attachment')


class RunJobTests(TestCase):
    def test_roda_job_pelo_nome(self):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('run_job', 'marcar_invoices_atrasados', stdout=out)
        self.assertIn("marcar_invoices_atrasados: {'data_execucao'", out.getvalue())

    def test_nome_invalido(self):
        from django.core.management import CommandError, call_command
        with self.assertRaises(CommandError):
            call_command('run_job', 'nao_existe')
