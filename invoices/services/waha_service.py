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

        # Remove o prefixo do pais (55) se presente
        if digits.startswith('55'):
            local = digits[2:]
        else:
            local = digits

        # local deve ter:
        #   11 digitos: DDD (2) + 9 + numero (8) → celular ja com o 9, manter
        #   10 digitos: DDD (2) + numero (8) → fixo ou celular sem o 9
        #     se o 1o digito do numero for 6-9, e celular → adicionar o 9
        #     se o 1o digito for 2-5, e fixo → manter sem o 9
        if len(local) == 10:
            primeiro_digito = local[2]
            if primeiro_digito in ('6', '7', '8', '9'):
                local = local[:2] + '9' + local[2:]

        return f"55{local}@c.us"

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
