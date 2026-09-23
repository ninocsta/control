"""Avisos pelo bot Telegram global.

Env: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (Team Shared Variables no Coolify) e,
opcional, TELEGRAM_THREAD_ID (tópico do grupo). Sem token/chat tudo vira no-op.
"""
import json
import logging
import os
import time
import traceback
import urllib.request

APP = "control"
THROTTLE_SECONDS = 600

log = logging.getLogger(__name__)


def notify(text):
    """Envia `[app] text`. Retorna True se o Telegram aceitou; nunca levanta exceção."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return False
    try:
        payload = {"chat_id": chat_id, "text": f"[{APP}] {text}"[:4000], "disable_web_page_preview": True}
        if thread_id := os.environ.get("TELEGRAM_THREAD_ID"):
            payload["message_thread_id"] = int(thread_id)
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception as e:  # HTTPError/URLError não trazem a URL (com o token) no str
        log.warning("telegram notify failed: %s", e)
        return False


_last_sent = {}


class TelegramErrorHandler(logging.Handler):
    """Ligado ao logger django.request (ERROR): avisa erro 500 no Telegram.

    ponytail: throttle em memória por processo (1 aviso igual por path+exceção a cada
    10 min); com N workers gunicorn podem chegar até N avisos iguais por janela.
    Usar o cache do Django se isso incomodar.
    """

    def emit(self, record):
        try:
            request = getattr(record, "request", None)
            where = f"{request.method} {request.path}" if request is not None else record.getMessage()
            exc_type, exc, tb = record.exc_info or (None, None, None)
            key = (where, exc_type.__name__ if exc_type else "")
            now = time.monotonic()
            if key in _last_sent and now - _last_sent[key] < THROTTLE_SECONDS:
                return
            _last_sent[key] = now
            lines = [f"🔥 Erro 500: {where}"]
            if exc_type:
                frames = traceback.extract_tb(tb)
                if frames:
                    f = frames[-1]
                    lines.append(f"{f.filename}:{f.lineno} em {f.name}")
                lines.append(traceback.format_exception_only(exc_type, exc)[-1].strip())
            else:
                lines.append(record.getMessage())
            notify("\n".join(lines)[:3500])
        except Exception:
            self.handleError(record)
