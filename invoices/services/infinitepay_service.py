from decimal import Decimal
import os
import logging
import re

from .http_client import post_json

logger = logging.getLogger(__name__)


class InfinitePayService:
    """
    Service para integracao com InfinitePay.
    """

    def __init__(self, base_url=None, api_key=None, handle=None, webhook_url=None, redirect_url=None, description=None, timeout=10):
        self.base_url = (base_url or os.getenv('INFINITEPAY_BASE_URL', 'https://api.infinitepay.io')).rstrip('/')
        self.api_key = api_key or os.getenv('INFINITEPAY_API_KEY', '')
        self.handle = handle or os.getenv('INFINITEPAY_HANDLE', '')
        self.webhook_url = webhook_url or os.getenv('INFINITEPAY_WEBHOOK_URL', '')
        self.redirect_url = redirect_url or os.getenv('INFINITEPAY_REDIRECT_URL', '')
        self.description = description or os.getenv('INFINITEPAY_ITEM_DESCRIPTION', 'Mensalidade de serviços contratados')
        self.timeout = timeout

    def _build_headers(self):
        headers = {}
        if self.api_key:
            headers['Authorization'] = f"Bearer {self.api_key}"
        return headers

    def _normalize_phone(self, phone):
        if not phone:
            return None
        digits = re.sub(r'\D', '', str(phone))
        if not digits:
            return None
        if not digits.startswith('55'):
            digits = f"55{digits}"
        return digits

    def _build_payload(self, invoice):
        if not self.handle or not self.webhook_url:
            raise ValueError('InfinitePay nao configurado (handle/webhook_url)')

        amount_cents = int((invoice.valor_total or Decimal('0.00')) * 100)
        payload = {
            'handle': self.handle,
            'items': [
                {
                    'quantity': 1,
                    'price': amount_cents,
                    'description': self.description,
                }
            ],
            'order_nsu': str(invoice.id),
            'webhook_url': self.webhook_url,
        }

        if self.redirect_url:
            payload['redirect_url'] = self.redirect_url

        cliente = invoice.cliente
        customer = {}
        nome = getattr(cliente, 'nome', None)
        email = getattr(cliente, 'email', None)
        telefone = getattr(cliente, 'telefone', None)

        if nome:
            customer['name'] = nome
        if email:
            customer['email'] = email
        telefone = self._normalize_phone(telefone)
        if telefone:
            customer['phone_number'] = telefone

        if customer:
            payload['customer'] = customer

        return payload

    def create_checkout(self, invoice):
        endpoint = f"{self.base_url}/invoices/public/checkout/links"
        payload = self._build_payload(invoice)
        response = post_json(endpoint, payload, headers=self._build_headers(), timeout=self.timeout)

        invoice.order_nsu = str(invoice.id)
        updated_fields = ['order_nsu']

        invoice_slug = response.get('invoice_slug') or response.get('invoiceSlug') or response.get('slug')
        checkout_url = response.get('checkout_url') or response.get('checkoutUrl') or response.get('url')

        if invoice_slug:
            invoice.invoice_slug = invoice_slug
            updated_fields.append('invoice_slug')
        if checkout_url:
            invoice.checkout_url = checkout_url
            updated_fields.append('checkout_url')

        invoice.save(update_fields=updated_fields)
        return response

    def try_create_checkout(self, invoice):
        try:
            return self.create_checkout(invoice)
        except Exception as exc:
            logger.error('Falha ao criar checkout InfinitePay para invoice %s: %s', invoice.id, exc)
            return None
