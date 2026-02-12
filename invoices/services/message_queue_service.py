import os
from django.utils import timezone

from invoices.models import MessageQueue


def _format_valor(valor):
    return f"R$ {valor:,.2f}"


def _format_periodo(invoice):
    return f"{invoice.mes_referencia:02d}/{invoice.ano_referencia}"

def _build_checkout_link(invoice):
    base_url = os.getenv('APP_BASE_URL') or os.getenv('PUBLIC_BASE_URL') or ''
    base_url = base_url.rstrip('/')

    ref = invoice.invoice_slug or invoice.order_nsu or str(invoice.id)
    if base_url and ref:
        return f"{base_url}/p/{ref}"

    return invoice.checkout_url or ''


def montar_mensagem_cobranca(invoice, tipo):
    periodo = _format_periodo(invoice)
    vencimento = invoice.vencimento.strftime('%d/%m/%Y')
    valor = _format_valor(invoice.valor_total)
    link = _build_checkout_link(invoice)

    if tipo == '5_dias':
        base = f"Oi! Lembrete: sua fatura {periodo} vence em {vencimento}. Valor: {valor}."
    elif tipo == '2_dias':
        base = f"Sua fatura {periodo} vence em {vencimento}. Valor: {valor}."
    else:
        base = f"Sua fatura {periodo} vence hoje ({vencimento}). Valor: {valor}."

    if link:
        return f"{base}\nClique aqui para realizar o pagamento: {link}"
    return base


def montar_mensagem_confirmacao(invoice):
    periodo = _format_periodo(invoice)
    valor = _format_valor(invoice.valor_total)
    return (
        f"Pagamento confirmado da fatura {periodo} no valor de {valor}. "
        "Muito obrigado pela parceria! Qualquer coisa, estou à disposição."
    )


def criar_mensagem_cobranca(invoice, tipo, agendado_para=None):
    if not invoice.cliente.telefone:
        return None, False

    agendado_para = agendado_para or timezone.now()
    mensagem = montar_mensagem_cobranca(invoice, tipo)

    return MessageQueue.objects.get_or_create(
        invoice=invoice,
        tipo=tipo,
        defaults={
            'telefone': invoice.cliente.telefone,
            'mensagem': mensagem,
            'agendado_para': agendado_para,
            'status': 'pendente',
        }
    )


def criar_mensagem_confirmacao(invoice, agendado_para=None):
    if not invoice.cliente.telefone:
        return None, False

    agendado_para = agendado_para or timezone.now()
    mensagem = montar_mensagem_confirmacao(invoice)

    return MessageQueue.objects.get_or_create(
        invoice=invoice,
        tipo='confirmacao',
        defaults={
            'telefone': invoice.cliente.telefone,
            'mensagem': mensagem,
            'agendado_para': agendado_para,
            'status': 'pendente',
        }
    )


def agendar_mensagens_cobranca(invoices, hoje=None):
    hoje = hoje or timezone.localdate()
    created = 0
    skipped = 0

    for invoice in invoices:
        delta = (invoice.vencimento - hoje).days
        if delta == 5:
            tipo = '5_dias'
        elif delta == 2:
            tipo = '2_dias'
        elif delta == 0:
            tipo = 'no_dia'
        else:
            skipped += 1
            continue

        _, is_created = criar_mensagem_cobranca(invoice, tipo)
        if is_created:
            created += 1
        else:
            skipped += 1

    return {
        'criados': created,
        'ignorados': skipped,
    }


def marcar_mensagem_enviada(message):
    message.status = 'enviado'
    message.enviado_em = timezone.now()
    message.save(update_fields=['status', 'enviado_em'])


def registrar_falha_envio(message, max_tentativas=3):
    message.tentativas += 1
    if message.tentativas >= max_tentativas:
        message.status = 'erro'
    message.save(update_fields=['tentativas', 'status'])
