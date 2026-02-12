import os
import re

from .http_client import post_json


class WahaService:
    """
    Service para envio de mensagens via WAHA.
    """

    def __init__(self, base_url=None, send_url=None, token=None, api_key=None, session=None, timeout=10):
        self.base_url = (base_url or os.getenv('WAHA_BASE_URL', '')).rstrip('/')
        self.send_url = send_url or os.getenv('WAHA_SEND_URL', '')
        self.token = token or os.getenv('WAHA_TOKEN', '')
        self.api_key = api_key or os.getenv('WAHA_API_KEY', '')
        self.session = session or os.getenv('WAHA_SESSION', 'default')
        self.timeout = timeout

    def _resolve_url(self):
        if self.send_url:
            return self.send_url
        if not self.base_url:
            raise ValueError('WAHA nao configurado (WAHA_BASE_URL ou WAHA_SEND_URL)')
        return f"{self.base_url}/api/sendText"

    def _build_headers(self):
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        if self.token:
            headers['Authorization'] = f"Bearer {self.token}"
        if self.api_key:
            headers['X-Api-Key'] = self.api_key
        return headers

    def _normalize_chat_id(self, telefone):
        if not telefone:
            return None
        telefone = telefone.strip()
        if '@c.us' in telefone or '@g.us' in telefone:
            return telefone

        digits = re.sub(r'\D', '', telefone)
        if digits.startswith('55'):
            local = digits[2:]
        else:
            local = digits

        if len(local) == 11:
            # Remove o '9' apos o DDD
            local = local[:2] + local[3:]

        if not local.startswith('55'):
            digits = f"55{local}"
        else:
            digits = local

        return f"{digits}@c.us"

    def send_message(self, telefone, mensagem):
        chat_id = self._normalize_chat_id(telefone)
        if not chat_id:
            raise ValueError('Telefone invalido para envio')

        url = self._resolve_url()
        payload = {
            'chatId': chat_id,
            'text': mensagem,
            'session': self.session,
        }
        return post_json(url, payload, headers=self._build_headers(), timeout=self.timeout)
