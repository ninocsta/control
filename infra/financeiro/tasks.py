"""
Jobs do módulo financeiro. Rodam por `manage.py run_job` (Scheduled Task do Coolify).

Tasks:
- Gerar período do mês atual
- Fechar período do mês anterior
- Resumo diário de datas (infra, contratos, reajustes) no Telegram
"""
from datetime import date, timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError

from app.notify import notify
import logging

from contratos.models import Contrato, ContratoReajuste
from infra.financeiro.models import PeriodoFinanceiro
from infra.financeiro.services import fechar_periodo
from infra.recursos.services import custos_monitorados

logger = logging.getLogger(__name__)


def task_gerar_periodo_mes_atual():
    """
    Cria o período financeiro do mês atual se não existir.
    
    Idempotente: não gera duplicatas.
    Executar: Todo dia 1 do mês.
    """
    hoje = timezone.localdate()
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


def task_fechar_periodo_mes_anterior():
    """
    Fecha o período financeiro do mês anterior se ainda estiver aberto.
    
    Idempotente: não recalcula períodos já fechados.
    Executar: Dia 1 de cada mês às 02:00.
    """
    hoje = timezone.localdate()
    
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
            usuario='Sistema Automático (Scheduled Task)'
        )
        
        logger.info(f"Período {periodo} fechado com sucesso: {resultado}")
        return {'status': 'closed', 'resultado': resultado}
        
    except PeriodoFinanceiro.DoesNotExist:
        logger.warning(f"Período {mes_anterior:02d}/{ano_anterior} não existe")
        return {'status': 'not_found', 'mes': mes_anterior, 'ano': ano_anterior}
        
    except ValidationError as e:
        logger.error(f"Erro ao fechar período: {e}")
        return {'status': 'error', 'message': str(e)}


DIAS_AVISO = (30, 15, 7, 3, 1, 0)
INTERVALO_AVISO_VENCIDO = 3  # vencido e não renovado: repete a cada N dias


def _deve_avisar(dias):
    return dias in DIAS_AVISO or (dias < 0 and -dias % INTERVALO_AVISO_VENCIDO == 0)


def _quando(dias):
    if dias == 0:
        return 'HOJE'
    if dias < 0:
        return f'vencido há {-dias}d'
    return f'em {dias}d'


def task_alertar_vencimentos():
    """
    Resumo diário no Telegram de tudo que tem data e não pode passar:
    - Renovação de infra (30/15/7/3/1/0 dias antes; vencido: a cada 3 dias até renovar/desativar)
    - Contratos terminando e reajustes entrando em vigor (30/7/0 dias)

    Renovou? Ação "Renovar" no admin do custo avança o vencimento.
    Executar: Diariamente às 08:00.
    """
    hoje = timezone.localdate()
    alertas = []

    for cost in custos_monitorados(ate=hoje + timedelta(days=max(DIAS_AVISO))):
        dias = (cost.vencimento - hoje).days
        if not _deve_avisar(dias):
            continue
        quem = ' · cliente paga' if cost.pago_pelo_cliente else f' · R$ {cost.valor_total:.2f}'
        alertas.append((dias, f"{cost.recurso}: {cost.vencimento:%d/%m} ({_quando(dias)}){quem}"))

    for contrato in Contrato.objects.filter(
        data_fim__gte=hoje, data_fim__lte=hoje + timedelta(days=30)
    ).select_related('cliente'):
        dias = (contrato.data_fim - hoje).days
        if dias in (30, 7, 0):
            alertas.append((dias, f"Contrato {contrato} termina {contrato.data_fim:%d/%m} ({_quando(dias)})"))

    for reajuste in ContratoReajuste.objects.filter(
        vigente_desde__gte=hoje, vigente_desde__lte=hoje + timedelta(days=30)
    ).select_related('contrato__cliente'):
        dias = (reajuste.vigente_desde - hoje).days
        if dias in (30, 7, 0):
            alertas.append((dias, f"Reajuste {reajuste.contrato}: R$ {reajuste.valor_mensal:.2f} "
                                  f"a partir de {reajuste.vigente_desde:%d/%m} ({_quando(dias)})"))

    if alertas:
        alertas.sort(key=lambda a: a[0])
        linhas = "\n".join(f"- {texto}" for _, texto in alertas[:40])
        notify(f"📅 {len(alertas)} data(s) para acompanhar:\n{linhas}")
    else:
        logger.info("Nenhum vencimento próximo encontrado")

    return {'total_alertas': len(alertas), 'alertas': [texto for _, texto in alertas]}
