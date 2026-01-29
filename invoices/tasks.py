"""
Tarefas assíncronas do Celery para o módulo de invoices.

Tasks:
- Gerar invoices mensais para todos os clientes
"""
from celery import shared_task
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.db import transaction, models
from django.core.exceptions import ValidationError
import logging
from decimal import Decimal

from invoices.models import Invoice
from clientes.models import Cliente
from contratos.models import Contrato

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def task_gerar_invoices_mes_atual(self):
    """
    Gera invoices de cobrança para todos os clientes com contratos ativos.
    
    Regras:
    - 1 invoice por cliente por mês
    - Valor = soma dos contratos ativos no mês
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
    clientes_sem_contrato = []
    erros = []
    
    # Buscar todos os clientes ativos
    clientes = Cliente.objects.filter(ativo=True)
    
    for cliente in clientes:
        try:
            # Verificar se já existe invoice para este cliente neste mês
            invoice_existente = Invoice.objects.filter(
                cliente=cliente,
                mes_referencia=mes,
                ano_referencia=ano
            ).first()
            
            if invoice_existente:
                invoices_existentes.append({
                    'cliente': cliente.nome,
                    'invoice_id': invoice_existente.id,
                    'valor': float(invoice_existente.valor_total)
                })
                logger.info(f"Invoice já existe para {cliente.nome} - {mes:02d}/{ano}")
                continue
            
            # Buscar contratos ativos do cliente no período
            # Ativo = data_inicio <= primeiro_dia_mes E (data_fim null OU data_fim >= primeiro_dia_mes)
            contratos_ativos = Contrato.objects.filter(
                cliente=cliente,
                data_inicio__lte=primeiro_dia_mes
            ).filter(
                models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia_mes)
            )
            
            if not contratos_ativos.exists():
                clientes_sem_contrato.append(cliente.nome)
                logger.info(f"Cliente {cliente.nome} não possui contratos ativos em {mes:02d}/{ano}")
                continue
            
            # Somar valores dos contratos ativos
            valor_total = sum(
                contrato.valor_mensal for contrato in contratos_ativos
            )
            
            if valor_total <= 0:
                logger.warning(f"Valor total zerado para {cliente.nome} - pulando invoice")
                continue
            
            # Criar invoice
            with transaction.atomic():
                invoice = Invoice.objects.create(
                    cliente=cliente,
                    mes_referencia=mes,
                    ano_referencia=ano,
                    valor_total=valor_total,
                    vencimento=vencimento,
                    status='pendente'
                )
                
                invoices_criados.append({
                    'cliente': cliente.nome,
                    'invoice_id': invoice.id,
                    'valor': float(valor_total),
                    'contratos': [c.nome for c in contratos_ativos]
                })
                
                logger.info(
                    f"Invoice criado: {invoice} - "
                    f"R$ {valor_total:,.2f} ({contratos_ativos.count()} contratos)"
                )
        
        except Exception as e:
            erros.append({
                'cliente': cliente.nome,
                'erro': str(e)
            })
            logger.error(f"Erro ao gerar invoice para {cliente.nome}: {e}")
    
    # Resumo da execução
    resultado = {
        'mes_referencia': f"{mes:02d}/{ano}",
        'total_clientes': clientes.count(),
        'invoices_criados': len(invoices_criados),
        'invoices_existentes': len(invoices_existentes),
        'clientes_sem_contrato': len(clientes_sem_contrato),
        'erros': len(erros),
        'detalhes': {
            'criados': invoices_criados,
            'existentes': invoices_existentes,
            'sem_contrato': clientes_sem_contrato,
            'erros': erros
        }
    }
    
    logger.info(
        f"Task concluída - {len(invoices_criados)} invoices criados, "
        f"{len(invoices_existentes)} já existiam, "
        f"{len(clientes_sem_contrato)} sem contrato, "
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
