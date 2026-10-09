import json
import logging

from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from app.notify import notify
from invoices.models import Invoice
from invoices.services.infinitepay_service import InfinitePayService
from invoices.services.invoice_service import registrar_pagamento
from invoices.tasks import task_enviar_confirmacao_imediata

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


def _centavos(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _conferir_na_infinitepay(invoice, transaction_nsu, invoice_slug):
    """
    Conferência paralela (não bloqueia a baixa): o webhook não é assinado, então confirma
    na API se o pagamento existe e avisa no Telegram se não bater.
    """
    try:
        check = InfinitePayService().verificar_pagamento(
            order_nsu=invoice.order_nsu or invoice.id,
            transaction_nsu=transaction_nsu,
            slug=invoice_slug or invoice.invoice_slug,
        )
    except Exception as exc:
        logger.warning('Conferencia InfinitePay falhou para invoice %s: %s', invoice.id, exc)
        notify(f"⚠️ Fatura {invoice.id} ({invoice.cliente.nome}) baixada pelo webhook, mas não consegui "
               f"conferir na InfinitePay: {exc}"[:500])
        return

    if check.get('paid') is not True:
        notify(f"🚨 Fatura {invoice.id} ({invoice.cliente.nome}) baixada pelo webhook, mas a InfinitePay "
               f"diz que NÃO está paga. Conferir.")
        return

    pago = _centavos(check.get('paid_amount') or check.get('amount'))
    esperado = int(invoice.valor_total * 100)
    if pago is not None and pago < esperado:
        notify(f"⚠️ Fatura {invoice.id} ({invoice.cliente.nome}) paga com valor menor: "
               f"R$ {pago / 100:.2f} de R$ {esperado / 100:.2f}")


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

    transaction_nsu = payload.get('transaction_nsu') or payload.get('transactionNsu') or ''
    try:
        with transaction.atomic():
            invoice = None
            if invoice_slug:
                invoice = Invoice.objects.select_for_update().filter(invoice_slug=invoice_slug).first()
            if not invoice and order_nsu:
                invoice = Invoice.objects.select_for_update().filter(order_nsu=order_nsu).first()
            if not invoice:
                raise Invoice.DoesNotExist
            ja_pago = invoice.status == 'pago'

            if invoice_slug and not invoice.invoice_slug:
                invoice.invoice_slug = invoice_slug
                invoice.save(update_fields=['invoice_slug'])
            mensagem = registrar_pagamento(
                invoice,
                transaction_nsu=transaction_nsu,
                receipt_url=payload.get('receipt_url') or payload.get('receiptUrl') or '',
                capture_method=payload.get('capture_method') or payload.get('captureMethod') or '',
            )
            if mensagem:
                # Depois do commit: o pagamento fica gravado mesmo se o WAHA falhar.
                transaction.on_commit(lambda: task_enviar_confirmacao_imediata(mensagem.id), robust=True)
    except Invoice.DoesNotExist:
        return HttpResponse(status=404)
    except Exception as exc:
        logger.error('Erro no webhook InfinitePay: %s', exc)
        return HttpResponse(status=500)

    if not ja_pago:
        _conferir_na_infinitepay(invoice, transaction_nsu, invoice_slug)

    return JsonResponse({'status': 'ok'})


def invoice_checkout_redirect(request, ref):
    invoice = Invoice.objects.filter(invoice_slug=ref).first()
    if not invoice:
        invoice = Invoice.objects.filter(order_nsu=ref).first()
    if not invoice and ref.isdigit():
        invoice = Invoice.objects.filter(id=int(ref)).first()
    if not invoice:
        return HttpResponse(status=404)
    if invoice.status == 'pago':
        if invoice.receipt_url:
            return redirect(invoice.receipt_url)
        return HttpResponse('Esta fatura já está paga. Obrigado!', content_type='text/plain; charset=utf-8')
    if invoice.status == 'cancelado':
        return HttpResponse('Esta fatura foi cancelada.', content_type='text/plain; charset=utf-8', status=410)
    if not invoice.checkout_url:
        return HttpResponse('Link de pagamento sendo gerado, tente novamente em instantes.',
                            content_type='text/plain; charset=utf-8', status=503)
    return redirect(invoice.checkout_url)
