"""
Tarefas assíncronas do Celery para o módulo financeiro.

Tasks:
- Gerar período do mês atual
- Fechar período do mês anterior
- Alertar vencimentos de infraestrutura
"""
from celery import shared_task
from datetime import date, timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
import logging

from infra.financeiro.models import PeriodoFinanceiro
from infra.financeiro.services import fechar_periodo
from infra.dominios.models import DomainCost
from infra.vps.models import VPSCost
from infra.emails.models import DomainEmailCost

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def task_gerar_periodo_mes_atual(self):
    """
    Cria o período financeiro do mês atual se não existir.
    
    Idempotente: não gera duplicatas.
    Executar: Todo dia 1 do mês.
    """
    hoje = date.today()
    mes = hoje.month
    ano = hoje.year
    
    periodo, criado = PeriodoFinanceiro.objects.get_or_create(
        mes=mes,
        ano=ano,
        defaults={
            'fechado': False,
            'observacoes': f'Período criado automaticamente em {timezone.now()}'
        }
    )
    
    if criado:
        logger.info(f"Período {periodo} criado com sucesso")
        return {'status': 'created', 'periodo': str(periodo)}
    else:
        logger.info(f"Período {periodo} já existe")
        return {'status': 'exists', 'periodo': str(periodo)}


@shared_task(bind=True, max_retries=3)
def task_fechar_periodo_mes_anterior(self):
    """
    Fecha o período financeiro do mês anterior se ainda estiver aberto.
    
    Idempotente: não recalcula períodos já fechados.
    Executar: Dia 1 de cada mês às 02:00.
    """
    hoje = date.today()
    
    # Calcular mês anterior
    primeiro_dia_mes_atual = date(hoje.year, hoje.month, 1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    
    mes_anterior = ultimo_dia_mes_anterior.month
    ano_anterior = ultimo_dia_mes_anterior.year
    
    try:
        periodo = PeriodoFinanceiro.objects.get(mes=mes_anterior, ano=ano_anterior)
        
        if periodo.fechado:
            logger.info(f"Período {periodo} já está fechado")
            return {'status': 'already_closed', 'periodo': str(periodo)}
        
        # Fechar período
        resultado = fechar_periodo(
            periodo_id=periodo.id,
            usuario='Sistema Automático (Celery)'
        )
        
        logger.info(f"Período {periodo} fechado com sucesso: {resultado}")
        return {'status': 'closed', 'resultado': resultado}
        
    except PeriodoFinanceiro.DoesNotExist:
        logger.warning(f"Período {mes_anterior:02d}/{ano_anterior} não existe")
        return {'status': 'not_found', 'mes': mes_anterior, 'ano': ano_anterior}
        
    except ValidationError as e:
        logger.error(f"Erro ao fechar período: {e}")
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True)
def task_alertar_vencimentos(self):
    """
    Envia alertas para custos de infraestrutura que vencem em breve.
    
    Regras:
    - Alerta 30 dias antes do vencimento
    - Alerta 7 dias antes do vencimento
    - Alerta no dia do vencimento
    
    Executar: Diariamente às 08:00.
    """
    hoje = date.today()
    datas_alerta = [
        hoje + timedelta(days=30),
        hoje + timedelta(days=7),
        hoje
    ]
    
    alertas = []
    
    # Domínios
    for data_alerta in datas_alerta:
        dominios_vencendo = DomainCost.objects.filter(
            vencimento=data_alerta,
            ativo=True
        ).select_related('domain')
        
        for cost in dominios_vencendo:
            dias = (cost.vencimento - hoje).days
            alertas.append({
                'tipo': 'dominio',
                'nome': cost.domain.nome,
                'vencimento': cost.vencimento.isoformat(),
                'dias_restantes': dias,
                'valor': float(cost.valor_total)
            })
    
    # VPS
    for data_alerta in datas_alerta:
        vps_vencendo = VPSCost.objects.filter(
            vencimento=data_alerta,
            ativo=True
        ).select_related('vps')
        
        for cost in vps_vencendo:
            dias = (cost.vencimento - hoje).days
            alertas.append({
                'tipo': 'vps',
                'nome': cost.vps.nome,
                'vencimento': cost.vencimento.isoformat(),
                'dias_restantes': dias,
                'valor': float(cost.valor_total)
            })
    
    # Emails
    for data_alerta in datas_alerta:
        emails_vencendo = DomainEmailCost.objects.filter(
            vencimento=data_alerta,
            ativo=True
        ).select_related('email__dominio', 'email__contrato__cliente')
        
        for cost in emails_vencendo:
            dias = (cost.vencimento - hoje).days
            alertas.append({
                'tipo': 'email',
                'dominio': cost.email.dominio.nome,
                'cliente': cost.email.contrato.cliente.nome,
                'contrato': cost.email.contrato.nome,
                'fornecedor': cost.email.fornecedor,
                'vencimento': cost.vencimento.isoformat(),
                'dias_restantes': dias,
                'valor': float(cost.valor_total)
            })
    
    if alertas:
        logger.warning(f"Encontrados {len(alertas)} vencimentos próximos")
        # TODO: Enviar email ou notificação
        # send_mail(...) ou criar modelo de Notificação
    else:
        logger.info("Nenhum vencimento próximo encontrado")
    
    return {'total_alertas': len(alertas), 'alertas': alertas}
