import os
import re

from .http_client import get_json, post_json


class ContactNotFoundError(Exception):
    """Numero de telefone nao encontrado no WhatsApp."""


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

    def _resolve_chat_id(self, telefone: str) -> str:
        """
        Valida o numero via /api/contacts/check-exists e retorna o chatId
        exato fornecido pela API do WAHA.

        Raises:
            ValueError: se o telefone estiver vazio ou sem digitos.
            ContactNotFoundError: se numberExists for False.
            RuntimeError: se a chamada HTTP falhar.
        """
        if not telefone:
            raise ValueError('Telefone nao informado')

        digits = re.sub(r'\D', '', telefone)
        if not digits:
            raise ValueError(f'Telefone invalido: {telefone!r}')

        if not digits.startswith('55'):
            digits = f'55{digits}'

        if not self.base_url:
            raise ValueError('WAHA nao configurado (WAHA_BASE_URL ausente)')

        url = f"{self.base_url}/api/contacts/check-exists"
        params = {'phone': digits, 'session': self.session}

        # Apenas X-Api-Key / Authorization — sem Content-Type em GETs
        headers = {k: v for k, v in self._build_headers().items() if k != 'Content-Type'}

        data = get_json(url, params=params, headers=headers, timeout=self.timeout)

        if not data.get('numberExists'):
            raise ContactNotFoundError(
                f'Numero {digits} nao encontrado no WhatsApp (numberExists=false)'
            )

        chat_id = data.get('chatId')
        if not chat_id:
            raise RuntimeError(f'WAHA retornou numberExists=true mas chatId ausente: {data}')

        return chat_id

    def send_message(self, telefone: str, mensagem: str) -> dict:
        chat_id = self._resolve_chat_id(telefone)

        url = self._resolve_url()
        payload = {
            'chatId': chat_id,
            'text': mensagem,
            'session': self.session,
        }
        return post_json(url, payload, headers=self._build_headers(), timeout=self.timeout)
