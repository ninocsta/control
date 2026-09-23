import json
import os
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import path

from . import notify as notify_mod
from .notify import notify

ENV = {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "42", "TELEGRAM_THREAD_ID": "7"}


def boom(request):
    raise ValueError("kaboom")


urlpatterns = [path("boom/", boom)]


class NotifyTests(SimpleTestCase):
    def setUp(self):
        notify_mod._last_sent.clear()

    @patch("urllib.request.urlopen")
    def test_noop_without_env(self, urlopen):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            self.assertFalse(notify("oi"))
        urlopen.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_sends_payload(self, urlopen):
        urlopen.return_value.__enter__.return_value.status = 200
        with patch.dict(os.environ, ENV):
            self.assertTrue(notify("oi"))
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "https://api.telegram.org/bottok/sendMessage")
        self.assertEqual(json.loads(req.data), {
            "chat_id": "42", "message_thread_id": 7, "disable_web_page_preview": True,
            "text": f"[{notify_mod.APP}] oi",
        })

    @patch("urllib.request.urlopen", side_effect=OSError("down"))
    def test_never_raises(self, urlopen):
        with patch.dict(os.environ, ENV), self.assertLogs(notify_mod.__name__, "WARNING"):
            self.assertFalse(notify("oi"))

    @override_settings(ROOT_URLCONF=__name__, DEBUG=False)
    def test_500_handler_with_throttle(self):
        self.client.raise_request_exception = False
        with patch.object(notify_mod, "notify") as send:
            self.assertEqual(self.client.get("/boom/").status_code, 500)
            self.assertEqual(self.client.get("/boom/").status_code, 500)
        send.assert_called_once()
        text = send.call_args.args[0]
        self.assertIn("GET /boom/", text)
        self.assertIn("ValueError: kaboom", text)
