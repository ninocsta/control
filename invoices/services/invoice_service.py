from datetime import date
from decimal import Decimal
import logging
from collections import defaultdict

from django.db import transaction, models
from django.utils import timezone

from contratos.models import Contrato
from invoices.models import Invoice, InvoiceContrato
from .infinitepay_service import InfinitePayService

logger = logging.getLogger(__name__)


def calcular_vencimento(cliente, mes, ano):
    dia = getattr(cliente, 'vencimento_padrao', 10) or 10
    dia = max(1, min(int(dia), 28))
    return date(ano, mes, dia)


def _buscar_contratos_ativos(mes, ano, cliente_nome=None):
    """Contratos cobráveis no mês: começaram até o dia 1 (início no meio do mês cobra a partir do seguinte)."""
    primeiro_dia_mes = date(ano, mes, 1)
    contratos = Contrato.objects.filter(
        data_inicio__lte=primeiro_dia_mes,
        cliente__ativo=True,
    ).filter(
        models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia_mes)
    ).select_related('cliente')

    if cliente_nome:
        contratos = contratos.filter(cliente__nome__icontains=cliente_nome)

    return contratos


def _contratos_ja_faturados(mes, ano):
    """Contratos que já estão numa mensalidade do mês (qualquer status: cancelada também conta, senão voltaria)."""
    return set(
        InvoiceContrato.objects.filter(
            invoice__tipo='mensal',
            invoice__mes_referencia=mes,
            invoice__ano_referencia=ano,
        ).values_list('contrato_id', flat=True)
    )


def gerar_invoices_mensais(mes=None, ano=None, cliente_nome=None):
    """
    Gera a mensalidade do mês. Idempotente por contrato: pode rodar todo dia; só cria fatura
    para contratos ainda não faturados no mês (ex.: contrato cadastrado depois do dia 1).
    """
    hoje = timezone.localdate()
    mes = mes or hoje.month
    ano = ano or hoje.year
    primeiro_dia = date(ano, mes, 1)

    contratos = _buscar_contratos_ativos(mes, ano, cliente_nome=cliente_nome)
    ja_faturados = _contratos_ja_faturados(mes, ano)

    contratos_por_cliente = defaultdict(list)
    for contrato in contratos:
        contratos_por_cliente[contrato.cliente_id].append(contrato)

    service = InfinitePayService()

    invoices_criados = []
    invoices_existentes = []
    clientes_sem_contrato = []
    erros = []

    for cliente_id, contratos_cliente in contratos_por_cliente.items():
        cliente = contratos_cliente[0].cliente

        try:
            pendentes = [c for c in contratos_cliente if c.id not in ja_faturados]
            if not pendentes:
                invoices_existentes.append({'cliente': cliente.nome})
                continue

            valores = {c.id: c.valor_em(primeiro_dia) for c in pendentes}
            pendentes = [c for c in pendentes if valores[c.id] > 0]
            total = sum((valores[c.id] for c in pendentes), Decimal('0.00'))

            if total <= 0:
                clientes_sem_contrato.append({
                    'cliente': cliente.nome,
                    'motivo': 'Valor total zerado',
                })
                continue

            with transaction.atomic():
                invoice = Invoice.objects.create(
                    cliente=cliente,
                    tipo='mensal',
                    mes_referencia=mes,
                    ano_referencia=ano,
                    valor_total=total,
                    vencimento=calcular_vencimento(cliente, mes, ano),
                    status='pendente',
                )
                invoice.order_nsu = str(invoice.id)
                invoice.save(update_fields=['order_nsu'])

                InvoiceContrato.objects.bulk_create([
                    InvoiceContrato(invoice=invoice, contrato=c, valor=valores[c.id])
                    for c in pendentes
                ])

            service.try_create_checkout(invoice)

            invoices_criados.append({
                'cliente': cliente.nome,
                'invoice_id': invoice.id,
                'valor': float(total),
                'contratos': [c.nome for c in pendentes],
            })

        except Exception as exc:
            logger.error('Erro ao gerar invoice para cliente %s: %s', cliente.nome, exc)
            erros.append({
                'cliente': cliente.nome,
                'erro': str(exc),
            })

    return {
        'mes_referencia': f"{mes:02d}/{ano}",
        'total_clientes': len(contratos_por_cliente),
        'invoices_criados': len(invoices_criados),
        'invoices_existentes': len(invoices_existentes),
        'clientes_sem_contrato': len(clientes_sem_contrato),
        'erros': len(erros),
        'detalhes': {
            'criados': invoices_criados,
            'existentes': invoices_existentes,
            'sem_contrato': clientes_sem_contrato,
            'erros': erros,
        }
    }


def recalcular_total(invoice):
    """valor_total = soma dos contratos vinculados. Se mudou e a fatura está em aberto, refaz o checkout."""
    total = invoice.itens_contrato.aggregate(t=models.Sum('valor'))['t']
    if total is None or total == invoice.valor_total:
        return False
    invoice.valor_total = total
    invoice.save(update_fields=['valor_total'])
    if invoice.em_aberto:
        invalidar_checkout(invoice)
        InfinitePayService().try_create_checkout(invoice)
    return True


def invalidar_checkout(invoice):
    """Esquece o link atual (valor mudou): a task de checkouts/recriação gera outro."""
    invoice.checkout_url = ''
    invoice.invoice_slug = None
    invoice.save(update_fields=['checkout_url', 'invoice_slug'])


def registrar_pagamento(invoice, pago_em=None, transaction_nsu='', receipt_url='', capture_method=''):
    """
    Baixa a fatura (webhook ou pagamento manual): marca pago, limpa cobranças pendentes e
    agenda a confirmação para o cliente. Retorna a MessageQueue de confirmação (ou None).
    """
    from .message_queue_service import criar_mensagem_confirmacao, remover_mensagens_cobranca_pendentes

    campos = []
    if invoice.status != 'pago':
        invoice.status = 'pago'
        campos.append('status')
    if not invoice.pago_em:
        invoice.pago_em = pago_em or timezone.now()
        campos.append('pago_em')
    for campo, valor in (('transaction_nsu', transaction_nsu), ('receipt_url', receipt_url),
                         ('capture_method', capture_method)):
        if valor and getattr(invoice, campo) != valor:
            setattr(invoice, campo, valor)
            campos.append(campo)
    if campos:
        invoice.save(update_fields=campos)

    remover_mensagens_cobranca_pendentes(invoice)
    mensagem, _ = criar_mensagem_confirmacao(invoice)
    return mensagem


def cancelar_fatura(invoice):
    """Cancela e limpa cobranças pendentes; o link /p/ passa a mostrar "cancelada"."""
    from .message_queue_service import remover_mensagens_cobranca_pendentes
    if invoice.status in ('pago', 'cancelado'):
        return False
    invoice.status = 'cancelado'
    invoice.save(update_fields=['status'])
    remover_mensagens_cobranca_pendentes(invoice)
    return True


def criar_avulsa(contrato, descricao, valor, vencimento):
    """Cobrança extra (horas, implantação...) ligada a um contrato; não bloqueia a mensalidade."""
    with transaction.atomic():
        invoice = Invoice.objects.create(
            cliente=contrato.cliente, tipo='avulsa', descricao=descricao, valor_total=valor,
            mes_referencia=vencimento.month, ano_referencia=vencimento.year, vencimento=vencimento,
        )
        invoice.order_nsu = str(invoice.id)
        invoice.save(update_fields=['order_nsu'])
        InvoiceContrato.objects.create(invoice=invoice, contrato=contrato, valor=valor)
    InfinitePayService().try_create_checkout(invoice)
    return invoice


def alterar_vencimento(invoice, vencimento):
    """Novo vencimento: volta a pendente se ainda não venceu e reinicia os lembretes."""
    from .message_queue_service import remover_mensagens_cobranca_pendentes
    invoice.vencimento = vencimento
    campos = ['vencimento']
    if invoice.status == 'atrasado' and vencimento >= timezone.localdate():
        invoice.status = 'pendente'
        campos.append('status')
    invoice.save(update_fields=campos)
    remover_mensagens_cobranca_pendentes(invoice)


def enviar_cobranca_agora(invoice):
    """Manda o lembrete no WhatsApp na hora (texto conforme a data: vence em / hoje / venceu)."""
    from .message_queue_service import montar_mensagem_cobranca
    from .waha_service import WahaService
    if not invoice.cliente.telefone:
        raise ValueError('Cliente sem telefone')
    if not invoice.checkout_url:
        InfinitePayService().try_create_checkout(invoice)
    texto = montar_mensagem_cobranca(invoice, 'no_dia', data_referencia=timezone.localdate())
    WahaService().send_message(invoice.cliente.telefone, texto)
