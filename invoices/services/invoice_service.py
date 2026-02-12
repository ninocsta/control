from datetime import date
from decimal import Decimal
import logging
from collections import defaultdict

from django.db import transaction, models

from contratos.models import Contrato
from invoices.models import Invoice, InvoiceContrato
from .infinitepay_service import InfinitePayService

logger = logging.getLogger(__name__)


def calcular_vencimento(cliente, mes, ano):
    dia = getattr(cliente, 'vencimento_padrao', 10) or 10
    dia = max(1, min(int(dia), 28))
    return date(ano, mes, dia)


def _buscar_contratos_ativos(mes, ano, cliente_nome=None):
    primeiro_dia_mes = date(ano, mes, 1)
    contratos = Contrato.objects.filter(
        data_inicio__lte=primeiro_dia_mes
    ).filter(
        models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia_mes)
    ).select_related('cliente')

    if cliente_nome:
        contratos = contratos.filter(cliente__nome__icontains=cliente_nome)

    return contratos


def gerar_invoices_mensais(mes=None, ano=None, cliente_nome=None):
    hoje = date.today()
    mes = mes or hoje.month
    ano = ano or hoje.year

    contratos = _buscar_contratos_ativos(mes, ano, cliente_nome=cliente_nome)

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
            invoice_existente = Invoice.objects.filter(
                cliente_id=cliente_id,
                mes_referencia=mes,
                ano_referencia=ano,
                itens_contrato__isnull=False,
            ).distinct().first()

            if invoice_existente:
                invoices_existentes.append({
                    'cliente': cliente.nome,
                    'invoice_id': invoice_existente.id,
                    'valor': float(invoice_existente.valor_total),
                })
                continue

            total = sum((c.valor_mensal for c in contratos_cliente), Decimal('0.00'))

            if total <= 0:
                clientes_sem_contrato.append({
                    'cliente': cliente.nome,
                    'motivo': 'Valor total zerado',
                })
                continue

            vencimento = calcular_vencimento(cliente, mes, ano)

            with transaction.atomic():
                invoice = Invoice.objects.create(
                    cliente=cliente,
                    mes_referencia=mes,
                    ano_referencia=ano,
                    valor_total=total,
                    vencimento=vencimento,
                    status='pendente',
                )
                invoice.order_nsu = str(invoice.id)
                invoice.save(update_fields=['order_nsu'])

                itens = []
                for contrato in contratos_cliente:
                    itens.append(InvoiceContrato(
                        invoice=invoice,
                        contrato=contrato,
                        valor=contrato.valor_mensal,
                    ))
                InvoiceContrato.objects.bulk_create(itens)

            service.try_create_checkout(invoice)

            invoices_criados.append({
                'cliente': cliente.nome,
                'invoice_id': invoice.id,
                'valor': float(total),
                'contratos': [c.nome for c in contratos_cliente],
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
