import json
import logging

from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction

from invoices.models import Invoice
from invoices.services.message_queue_service import criar_mensagem_confirmacao

logger = logging.getLogger(__name__)


def _extrair_invoice_slug(payload):
    for key in ('invoice_slug', 'invoiceSlug', 'slug'):
        if payload.get(key):
            return payload.get(key)

    invoice_obj = payload.get('invoice')
    if isinstance(invoice_obj, dict):
        for key in ('invoice_slug', 'invoiceSlug', 'slug'):
            if invoice_obj.get(key):
                return invoice_obj.get(key)

    return None


def _extrair_order_nsu(payload):
    for key in ('order_nsu', 'orderNsu'):
        if payload.get(key):
            return payload.get(key)

    invoice_obj = payload.get('invoice')
    if isinstance(invoice_obj, dict):
        for key in ('order_nsu', 'orderNsu'):
            if invoice_obj.get(key):
                return invoice_obj.get(key)

    return None


@csrf_exempt
def infinitepay_webhook(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        payload = request.POST.dict()

    invoice_slug = _extrair_invoice_slug(payload)
    order_nsu = _extrair_order_nsu(payload)
    if not invoice_slug and not order_nsu:
        return HttpResponseBadRequest('invoice_slug/order_nsu ausente')

    try:
        with transaction.atomic():
            invoice = None
            if invoice_slug:
                invoice = Invoice.objects.filter(invoice_slug=invoice_slug).first()
            if not invoice and order_nsu:
                invoice = Invoice.objects.filter(order_nsu=order_nsu).first()
            if not invoice:
                raise Invoice.DoesNotExist

            updated_fields = []
            if invoice.status != 'pago':
                invoice.status = 'pago'
                invoice.pago_em = timezone.now()
                updated_fields.extend(['status', 'pago_em'])

            transaction_nsu = payload.get('transaction_nsu') or payload.get('transactionNsu')
            receipt_url = payload.get('receipt_url') or payload.get('receiptUrl')
            capture_method = payload.get('capture_method') or payload.get('captureMethod')

            if transaction_nsu and invoice.transaction_nsu != transaction_nsu:
                invoice.transaction_nsu = transaction_nsu
                updated_fields.append('transaction_nsu')
            if receipt_url and invoice.receipt_url != receipt_url:
                invoice.receipt_url = receipt_url
                updated_fields.append('receipt_url')
            if capture_method and invoice.capture_method != capture_method:
                invoice.capture_method = capture_method
                updated_fields.append('capture_method')

            if invoice_slug and not invoice.invoice_slug:
                invoice.invoice_slug = invoice_slug
                updated_fields.append('invoice_slug')
            if order_nsu and not invoice.order_nsu:
                invoice.order_nsu = order_nsu
                updated_fields.append('order_nsu')

            if updated_fields:
                invoice.save(update_fields=updated_fields)

            criar_mensagem_confirmacao(invoice)

    except Invoice.DoesNotExist:
        return HttpResponse(status=404)
    except Exception as exc:
        logger.error('Erro no webhook InfinitePay: %s', exc)
        return HttpResponse(status=500)

    return JsonResponse({'status': 'ok'})


def invoice_checkout_redirect(request, ref):
    invoice = Invoice.objects.filter(invoice_slug=ref).first()
    if not invoice:
        invoice = Invoice.objects.filter(order_nsu=ref).first()
    if not invoice and ref.isdigit():
        invoice = Invoice.objects.filter(id=int(ref)).first()
    if not invoice or not invoice.checkout_url:
        return HttpResponse(status=404)
    return redirect(invoice.checkout_url)
