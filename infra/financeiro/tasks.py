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
from django.core.mail import send_mail
from django.conf import settings
import logging

from infra.financeiro.models import PeriodoFinanceiro
from infra.financeiro.services import fechar_periodo
from infra.dominios.models import DomainCost
from infra.vps.models import VPSCost
from infra.emails.models import DomainEmailCost
from infra.hosting.models import HostingCost
from infra.backups.models import VPSBackupCost

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
                'tipo': 'Domínio',
                'nome': cost.domain.nome,
                'fornecedor': cost.domain.fornecedor,
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
                'tipo': 'VPS',
                'nome': cost.vps.nome,
                'fornecedor': cost.vps.fornecedor,
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
                'tipo': 'Email',
                'nome': f"{cost.email.dominio.nome}",
                'fornecedor': cost.email.fornecedor,
                'cliente': cost.email.contrato.cliente.nome,
                'contrato': cost.email.contrato.nome,
                'vencimento': cost.vencimento.isoformat(),
                'dias_restantes': dias,
                'valor': float(cost.valor_total)
            })
    
    # Hosting
    for data_alerta in datas_alerta:
        hostings_vencendo = HostingCost.objects.filter(
            vencimento=data_alerta,
            ativo=True
        ).select_related('hosting')
        
        for cost in hostings_vencendo:
            dias = (cost.vencimento - hoje).days
            alertas.append({
                'tipo': 'Hosting',
                'nome': cost.hosting.nome,
                'fornecedor': cost.hosting.fornecedor,
                'vencimento': cost.vencimento.isoformat(),
                'dias_restantes': dias,
                'valor': float(cost.valor_total)
            })
    
    # Backups de VPS
    for data_alerta in datas_alerta:
        backups_vencendo = VPSBackupCost.objects.filter(
            vencimento=data_alerta,
            ativo=True
        ).select_related('backup__vps')
        
        for cost in backups_vencendo:
            dias = (cost.vencimento - hoje).days
            alertas.append({
                'tipo': 'Backup VPS',
                'nome': f"{cost.backup.nome} ({cost.backup.vps.nome})",
                'fornecedor': cost.backup.fornecedor or cost.backup.vps.fornecedor,
                'vencimento': cost.vencimento.isoformat(),
                'dias_restantes': dias,
                'valor': float(cost.valor_total)
            })
    
    if alertas:
        logger.warning(f"Encontrados {len(alertas)} vencimentos próximos")
        
        # Enviar email com os alertas
        try:
            enviar_email_alertas(alertas, hoje)
            logger.info(f"Email de alertas enviado com sucesso para {settings.ALERT_EMAIL_RECIPIENT}")
        except Exception as e:
            logger.error(f"Erro ao enviar email de alertas: {e}")
    else:
        logger.info("Nenhum vencimento próximo encontrado")
    
    return {'total_alertas': len(alertas), 'alertas': alertas}


def enviar_email_alertas(alertas, data_referencia):
    """
    Envia email formatado com os alertas de vencimento.
    """
    # Agrupar alertas por dias restantes
    hoje = []
    sete_dias = []
    trinta_dias = []
    
    for alerta in alertas:
        if alerta['dias_restantes'] == 0:
            hoje.append(alerta)
        elif alerta['dias_restantes'] == 7:
            sete_dias.append(alerta)
        elif alerta['dias_restantes'] == 30:
            trinta_dias.append(alerta)
    
    # Construir corpo do email
    corpo_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            h2 {{ color: #333; }}
            h3 {{ color: #666; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th {{ background-color: #4CAF50; color: white; padding: 10px; text-align: left; }}
            td {{ border: 1px solid #ddd; padding: 8px; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .urgente {{ background-color: #ffebee !important; }}
            .atencao {{ background-color: #fff3e0 !important; }}
            .info {{ background-color: #e3f2fd !important; }}
        </style>
    </head>
    <body>
        <h2>🔔 Alertas de Vencimento de Infraestrutura</h2>
        <p><strong>Data:</strong> {data_referencia.strftime('%d/%m/%Y')}</p>
        <p><strong>Total de Alertas:</strong> {len(alertas)}</p>
        <hr>
    """
    
    # Alertas de HOJE
    if hoje:
        corpo_html += f"""
        <h3 style="color: #d32f2f;">🚨 VENCENDO HOJE ({len(hoje)})</h3>
        <table>
            <tr>
                <th>Tipo</th>
                <th>Nome</th>
                <th>Fornecedor</th>
                <th>Vencimento</th>
                <th>Valor</th>
            </tr>
        """
        for alerta in hoje:
            corpo_html += f"""
            <tr class="urgente">
                <td>{alerta['tipo']}</td>
                <td>{alerta['nome']}</td>
                <td>{alerta.get('fornecedor', '-')}</td>
                <td>{alerta['vencimento']}</td>
                <td>R$ {alerta['valor']:.2f}</td>
            </tr>
            """
        corpo_html += "</table>"
    
    # Alertas de 7 DIAS
    if sete_dias:
        corpo_html += f"""
        <h3 style="color: #f57c00;">⚠️ VENCENDO EM 7 DIAS ({len(sete_dias)})</h3>
        <table>
            <tr>
                <th>Tipo</th>
                <th>Nome</th>
                <th>Fornecedor</th>
                <th>Vencimento</th>
                <th>Valor</th>
            </tr>
        """
        for alerta in sete_dias:
            corpo_html += f"""
            <tr class="atencao">
                <td>{alerta['tipo']}</td>
                <td>{alerta['nome']}</td>
                <td>{alerta.get('fornecedor', '-')}</td>
                <td>{alerta['vencimento']}</td>
                <td>R$ {alerta['valor']:.2f}</td>
            </tr>
            """
        corpo_html += "</table>"
    
    # Alertas de 30 DIAS
    if trinta_dias:
        corpo_html += f"""
        <h3 style="color: #1976d2;">ℹ️ VENCENDO EM 30 DIAS ({len(trinta_dias)})</h3>
        <table>
            <tr>
                <th>Tipo</th>
                <th>Nome</th>
                <th>Fornecedor</th>
                <th>Vencimento</th>
                <th>Valor</th>
            </tr>
        """
        for alerta in trinta_dias:
            corpo_html += f"""
            <tr class="info">
                <td>{alerta['tipo']}</td>
                <td>{alerta['nome']}</td>
                <td>{alerta.get('fornecedor', '-')}</td>
                <td>{alerta['vencimento']}</td>
                <td>R$ {alerta['valor']:.2f}</td>
            </tr>
            """
        corpo_html += "</table>"
    
    # Resumo financeiro
    total_hoje = sum(a['valor'] for a in hoje)
    total_7dias = sum(a['valor'] for a in sete_dias)
    total_30dias = sum(a['valor'] for a in trinta_dias)
    total_geral = total_hoje + total_7dias + total_30dias
    
    corpo_html += f"""
        <hr>
        <h3>💰 Resumo Financeiro</h3>
        <table>
            <tr>
                <th>Período</th>
                <th>Quantidade</th>
                <th>Valor Total</th>
            </tr>
            <tr class="urgente">
                <td>Hoje</td>
                <td>{len(hoje)}</td>
                <td>R$ {total_hoje:.2f}</td>
            </tr>
            <tr class="atencao">
                <td>7 dias</td>
                <td>{len(sete_dias)}</td>
                <td>R$ {total_7dias:.2f}</td>
            </tr>
            <tr class="info">
                <td>30 dias</td>
                <td>{len(trinta_dias)}</td>
                <td>R$ {total_30dias:.2f}</td>
            </tr>
            <tr style="font-weight: bold;">
                <td>TOTAL</td>
                <td>{len(alertas)}</td>
                <td>R$ {total_geral:.2f}</td>
            </tr>
        </table>
        <hr>
        <p style="color: #666; font-size: 12px;">
            Este é um email automático do sistema de controle de infraestrutura.<br>
            Para mais informações, acesse o painel administrativo.
        </p>
    </body>
    </html>
    """
    
    # Enviar email
    assunto = f"🔔 Alertas de Vencimento - {len(alertas)} item(s) - {data_referencia.strftime('%d/%m/%Y')}"
    
    send_mail(
        subject=assunto,
        message="Este email requer visualização em HTML.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.ALERT_EMAIL_RECIPIENT],
        html_message=corpo_html,
        fail_silently=False,
    )
