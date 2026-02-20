"""
Tarefas assíncronas do Celery para o módulo de invoices.
"""
from celery import shared_task
from datetime import date
from django.utils import timezone
from django.db import models
import logging

from invoices.models import Invoice, MessageQueue
from invoices.services.invoice_service import gerar_invoices_mensais
from invoices.services.infinitepay_service import InfinitePayService
from invoices.services.message_queue_service import (
    agendar_mensagens_cobranca,
    agendar_mensagens_atraso,
    registrar_falha_envio,
    marcar_mensagem_enviada,
)
from invoices.services.waha_service import WahaService
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def task_gerar_invoices_mes_atual(self):
    """
    Gera invoices de cobrança para todos os clientes com contratos ativos.
    
    Regras:
    - 1 invoice por cliente por mês
    - Valor = soma dos contratos ativos no mês
    - Vencimento = cliente.vencimento_padrao (1-28)
    - Idempotente: não gera duplicatas
    
    Executar: Todo dia 1 do mês às 00:10.
    """
    resultado = gerar_invoices_mensais()

    logger.info(
        "Task concluida - %s invoices criados, %s ja existiam, %s sem contrato, %s erros",
        resultado['invoices_criados'],
        resultado['invoices_existentes'],
        resultado['clientes_sem_contrato'],
        resultado['erros'],
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


@shared_task(bind=True, max_retries=3)
def task_agendar_mensagens_cobranca(self):
    """
    Agenda mensagens de cobrança para invoices pendentes.

    Regras:
    - 5 dias antes
    - 2 dias antes
    - No dia do vencimento

    Executar: Diariamente.
    """
    hoje = timezone.localdate()
    invoices_pendentes = Invoice.objects.filter(
        status='pendente',
        vencimento__gte=hoje,
    ).select_related('cliente')

    resultado = agendar_mensagens_cobranca(invoices_pendentes, hoje=hoje)

    logger.info(
        "Mensagens agendadas: %s criadas, %s ignoradas",
        resultado['criados'],
        resultado['ignorados'],
    )
    return resultado


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def task_enviar_confirmacao_imediata(self, messagequeue_id):
    """
    Envia imediatamente a mensagem de confirmacao de pagamento via WAHA.

    Disparada pelo webhook da InfinitePay logo apos registrar o pagamento.
    Faz ate 3 tentativas com 30s de intervalo.
    Caso todas falhem, o registro permanece na fila com status 'erro' e
    o task_processar_fila_waha horario tenta novamente como fallback.
    """
    try:
        mensagem = MessageQueue.objects.select_related('invoice', 'invoice__cliente').get(
            pk=messagequeue_id,
            tipo='confirmacao',
        )
    except MessageQueue.DoesNotExist:
        logger.error('task_enviar_confirmacao_imediata: MessageQueue %s nao encontrada', messagequeue_id)
        return

    if mensagem.status == 'enviado':
        logger.info('Confirmacao %s ja enviada, ignorando', messagequeue_id)
        return

    if not mensagem.telefone:
        logger.warning('Confirmacao %s sem telefone, marcando erro', messagequeue_id)
        registrar_falha_envio(mensagem)
        return

    try:
        WahaService().send_message(mensagem.telefone, mensagem.mensagem)
        marcar_mensagem_enviada(mensagem)
        logger.info('Confirmacao %s enviada com sucesso', messagequeue_id)
    except Exception as exc:
        logger.warning('Falha ao enviar confirmacao %s (tentativa %s): %s', messagequeue_id, self.request.retries + 1, exc)
        registrar_falha_envio(mensagem)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def task_processar_fila_waha(self, limite=1):
    """
    Processa a fila de mensagens pendentes e envia via WAHA.

    Executar: A cada hora.
    """
    agora = timezone.now()
    tipos_cobranca = ['5_dias', '2_dias', 'no_dia', 'atraso']
    mensagens = MessageQueue.objects.filter(
        status='pendente',
        agendado_para__lte=agora
    ).filter(
        models.Q(tipo='confirmacao') |
        (
            models.Q(tipo__in=tipos_cobranca) &
            models.Q(invoice__checkout_url__isnull=False) &
            ~models.Q(invoice__checkout_url='')
        )
    ).select_related('invoice').order_by('agendado_para')[:limite]

    service = WahaService()
    enviados = 0
    falhas = 0

    for mensagem in mensagens:
        try:
            if not mensagem.telefone:
                logger.warning('Mensagem %s sem telefone, marcando erro', mensagem.id)
                registrar_falha_envio(mensagem)
                falhas += 1
                continue
            service.send_message(mensagem.telefone, mensagem.mensagem)
            marcar_mensagem_enviada(mensagem)
            enviados += 1
        except Exception as exc:
            logger.error('Falha ao enviar mensagem %s: %s', mensagem.id, exc)
            registrar_falha_envio(mensagem)
            falhas += 1

    return {
        'processadas': len(mensagens),
        'enviadas': enviados,
        'falhas': falhas,
    }


@shared_task(bind=True, max_retries=3)
def task_agendar_mensagens_atraso(self):
    """
    Agenda mensagens de atraso a cada 3 dias apos o vencimento.

    Executar: Diariamente.
    """
    hoje = timezone.localdate()
    invoices_atrasadas = Invoice.objects.filter(
        vencimento__lt=hoje,
        status__in=['pendente', 'atrasado'],
    ).select_related('cliente')

    resultado = agendar_mensagens_atraso(invoices_atrasadas, hoje=hoje)

    logger.info(
        "Mensagens de atraso: %s criadas, %s ignoradas",
        resultado['criados'],
        resultado['ignorados'],
    )
    return resultado


@shared_task(bind=True, max_retries=3)
def task_processar_checkouts_infinitepay(self, limite=100):
    """
    Reprocessa invoices pendentes sem checkout InfinitePay (retry seguro).

    Executar: Periodicamente.
    """
    invoices = Invoice.objects.filter(
        status='pendente',
    ).filter(
        models.Q(checkout_url='') | models.Q(checkout_url__isnull=True) |
        models.Q(invoice_slug='') | models.Q(invoice_slug__isnull=True)
    ).select_related('cliente')[:limite]

    service = InfinitePayService()
    processadas = 0
    sucessos = 0
    falhas = 0

    for invoice in invoices:
        processadas += 1
        result = service.try_create_checkout(invoice)
        if result:
            sucessos += 1
        else:
            falhas += 1

    return {
        'processadas': processadas,
        'sucessos': sucessos,
        'falhas': falhas,
    }
