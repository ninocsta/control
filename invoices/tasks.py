"""
Tarefas assíncronas do Celery para o módulo de invoices.

Tasks:
- Gerar invoices mensais para todos os contratos
"""
from celery import shared_task
from datetime import date
from django.db import transaction, models
import logging

from invoices.models import Invoice, InvoiceContrato
from contratos.models import Contrato

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def task_gerar_invoices_mes_atual(self):
    """
    Gera invoices de cobrança para todos os contratos ativos.
    
    Regras:
    - 1 invoice por contrato por mês
    - Valor = valor_mensal do contrato
    - Vencimento = dia 5 do mês de referência
    - Idempotente: não gera duplicatas
    
    Executar: Todo dia 1 do mês às 00:10.
    """
    hoje = date.today()
    mes = hoje.month
    ano = hoje.year
    
    # Data de vencimento padrão: dia 10 do mês
    vencimento = date(ano, mes, 10)
    
    # Primeiro dia do mês para validação de contratos ativos
    primeiro_dia_mes = date(ano, mes, 1)
    
    invoices_criados = []
    invoices_existentes = []
    contratos_sem_invoice = []
    clientes_com_invoice_sem_vinculo = set()
    erros = []
    
    # Clientes com invoice do período sem vínculo (evitar duplicação)
    invoices_sem_vinculo = Invoice.objects.filter(
        mes_referencia=mes,
        ano_referencia=ano,
        itens_contrato__isnull=True
    ).values_list('cliente_id', flat=True)
    clientes_com_invoice_sem_vinculo = set(invoices_sem_vinculo)
    
    # Buscar contratos ativos
    contratos_ativos = Contrato.objects.filter(
        data_inicio__lte=primeiro_dia_mes
    ).filter(
        models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia_mes)
    ).select_related('cliente')
    
    for contrato in contratos_ativos:
        try:
            # Evitar duplicação se já existe invoice sem vínculo para o cliente
            if contrato.cliente_id in clientes_com_invoice_sem_vinculo:
                logger.warning(
                    f"Cliente {contrato.cliente.nome} já possui invoice sem vínculo em {mes:02d}/{ano} - "
                    f"pulando contrato {contrato.nome}"
                )
                contratos_sem_invoice.append({
                    'contrato': contrato.nome,
                    'cliente': contrato.cliente.nome,
                    'motivo': 'Cliente já possui invoice sem vínculo no período'
                })
                continue
            
            # Verificar se já existe invoice para este contrato neste mês
            invoice_existente = InvoiceContrato.objects.filter(
                contrato=contrato,
                invoice__mes_referencia=mes,
                invoice__ano_referencia=ano
            ).select_related('invoice').first()
            
            if invoice_existente:
                invoices_existentes.append({
                    'cliente': contrato.cliente.nome,
                    'contrato': contrato.nome,
                    'invoice_id': invoice_existente.invoice.id,
                    'valor': float(invoice_existente.invoice.valor_total)
                })
                logger.info(
                    f"Invoice já existe para contrato {contrato.nome} - {mes:02d}/{ano}"
                )
                continue
            
            valor_total = contrato.valor_mensal
            
            if valor_total <= 0:
                logger.warning(
                    f"Valor total zerado para contrato {contrato.nome} - pulando invoice"
                )
                contratos_sem_invoice.append({
                    'contrato': contrato.nome,
                    'cliente': contrato.cliente.nome,
                    'motivo': 'Valor mensal zerado'
                })
                continue
            
            # Criar invoice
            with transaction.atomic():
                invoice = Invoice.objects.create(
                    cliente=contrato.cliente,
                    mes_referencia=mes,
                    ano_referencia=ano,
                    valor_total=valor_total,
                    vencimento=vencimento,
                    status='pendente'
                )
                
                # Criar vínculo invoice ↔ contrato (receita por contrato)
                InvoiceContrato.objects.create(
                    invoice=invoice,
                    contrato=contrato,
                    valor=contrato.valor_mensal
                )
                
                invoices_criados.append({
                    'cliente': contrato.cliente.nome,
                    'contrato': contrato.nome,
                    'invoice_id': invoice.id,
                    'valor': float(valor_total)
                })
                
                logger.info(
                    f"Invoice criado: {invoice} - "
                    f"R$ {valor_total:,.2f} (contrato {contrato.nome})"
                )
        
        except Exception as e:
            erros.append({
                'cliente': contrato.cliente.nome,
                'contrato': contrato.nome,
                'erro': str(e)
            })
            logger.error(
                f"Erro ao gerar invoice para contrato {contrato.nome}: {e}"
            )
    
    # Resumo da execução
    resultado = {
        'mes_referencia': f"{mes:02d}/{ano}",
        'total_contratos': contratos_ativos.count(),
        'invoices_criados': len(invoices_criados),
        'invoices_existentes': len(invoices_existentes),
        'contratos_sem_invoice': len(contratos_sem_invoice),
        'erros': len(erros),
        'detalhes': {
            'criados': invoices_criados,
            'existentes': invoices_existentes,
            'sem_invoice': contratos_sem_invoice,
            'erros': erros
        }
    }
    
    logger.info(
        f"Task concluída - {len(invoices_criados)} invoices criados, "
        f"{len(invoices_existentes)} já existiam, "
        f"{len(contratos_sem_invoice)} sem invoice, "
        f"{len(erros)} erros"
    )
    
    return resultado


@shared_task(bind=True, max_retries=3)
def task_marcar_invoices_atrasados(self):
    """
    Marca invoices como 'atrasado' quando passam do vencimento.
    
    Regras:
    - Somente invoices com status 'pendente'
    - Vencimento < hoje
    
    Executar: Diariamente às 09:00.
    """
    hoje = date.today()
    
    # Buscar invoices pendentes e vencidos
    invoices_vencidos = Invoice.objects.filter(
        status='pendente',
        vencimento__lt=hoje
    )
    
    total_atualizados = 0
    detalhes = []
    
    for invoice in invoices_vencidos:
        dias_atraso = (hoje - invoice.vencimento).days
        
        invoice.status = 'atrasado'
        invoice.save(update_fields=['status'])
        
        total_atualizados += 1
        detalhes.append({
            'invoice_id': invoice.id,
            'cliente': invoice.cliente.nome,
            'periodo': f"{invoice.mes_referencia:02d}/{invoice.ano_referencia}",
            'vencimento': invoice.vencimento.isoformat(),
            'dias_atraso': dias_atraso,
            'valor': float(invoice.valor_total)
        })
        
        logger.warning(
            f"Invoice {invoice.id} marcado como atrasado - "
            f"{invoice.cliente.nome} - {dias_atraso} dias"
        )
    
    resultado = {
        'data_execucao': hoje.isoformat(),
        'total_atualizados': total_atualizados,
        'detalhes': detalhes
    }
    
    if total_atualizados > 0:
        logger.warning(f"{total_atualizados} invoices marcados como atrasados")
        # TODO: Enviar notificação/email para cobrança
    else:
        logger.info("Nenhum invoice atrasado encontrado")
    
    return resultado
