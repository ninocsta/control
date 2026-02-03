"""
Service de fechamento de período financeiro.

Responsável por:
- Calcular custos ativos no período
- Fazer rateio proporcional por contrato
- Gerar snapshots imutáveis
- Marcar período como fechado
"""
from decimal import Decimal
from datetime import date
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from collections import defaultdict

from infra.financeiro.models import PeriodoFinanceiro, ContratoSnapshot, DespesaAdicional
from contratos.models import Contrato
from invoices.models import InvoiceContrato
from infra.dominios.models import DomainCost
from infra.hosting.models import HostingCost
from infra.vps.models import VPSCost
from infra.backups.models import VPSBackupCost
from infra.emails.models import DomainEmailCost
from .rateio import calcular_custo_mensal, ratear_por_contratos, validar_periodo


def fechar_periodo(periodo_id: int, usuario: str) -> dict:
    """
    Fecha um período financeiro, calculando custos e gerando snapshots.
    
    Args:
        periodo_id: ID do PeriodoFinanceiro
        usuario: Nome/email do usuário que está fechando
    
    Returns:
        dict: Estatísticas do fechamento (contratos processados, custos, etc)
    
    Raises:
        ValidationError: Se período já está fechado ou dados inválidos
    """
    with transaction.atomic():
        # 1. Buscar e validar período
        periodo = PeriodoFinanceiro.objects.select_for_update().get(id=periodo_id)
        validar_periodo(periodo)
        
        # 2. Calcular datas do período
        primeiro_dia = date(periodo.ano, periodo.mes, 1)
        if periodo.mes == 12:
            ultimo_dia = date(periodo.ano + 1, 1, 1)
        else:
            ultimo_dia = date(periodo.ano, periodo.mes + 1, 1)
        
        # 3. Buscar contratos ativos no período
        contratos_ativos = Contrato.objects.filter(
            data_inicio__lt=ultimo_dia
        ).filter(
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia)
        ).select_related('cliente').prefetch_related(
            'dominios', 'hostings', 'vps_list'
        )
        
        if not contratos_ativos.exists():
            raise ValidationError(
                f"Nenhum contrato ativo encontrado para o período {periodo}"
            )
        
        # 4. Coletar todos os custos ativos no período
        custos_por_tipo = _coletar_custos_periodo(primeiro_dia, ultimo_dia)
        
        # 5. Calcular rateio por contrato
        rateios_por_contrato = _calcular_rateios(
            contratos_ativos,
            custos_por_tipo,
            primeiro_dia,
            ultimo_dia
        )
        
        # 6. Criar snapshots
        snapshots_criados = []
        for contrato in contratos_ativos:
            snapshot = _criar_snapshot(
                contrato,
                periodo,
                rateios_por_contrato[contrato.id]
            )
            snapshots_criados.append(snapshot)
        
        # 7. Marcar período como fechado
        periodo.fechado = True
        periodo.fechado_em = timezone.now()
        periodo.fechado_por = usuario
        periodo.save()
        
        # 8. Retornar estatísticas
        return {
            'periodo': str(periodo),
            'contratos_processados': len(snapshots_criados),
            'receita_total': sum(s.receita for s in snapshots_criados),
            'custo_total': sum(s.custo_total for s in snapshots_criados),
            'margem_total': sum(s.margem for s in snapshots_criados),
        }


def _coletar_custos_periodo(primeiro_dia: date, ultimo_dia: date) -> dict:
    """
    Coleta todos os custos de infraestrutura ativos no período.
    
    Returns:
        dict: {
            'dominios': QuerySet,
            'hostings': QuerySet,
            'vps': QuerySet,
            'backups': QuerySet,
            'emails': QuerySet
        }
    """
    filtro_periodo = {
        'data_inicio__lt': ultimo_dia,
        'ativo': True,
    }
    
    # Custos que não têm data_fim OU têm data_fim >= primeiro_dia
    
    return {
        'dominios': DomainCost.objects.filter(
            **filtro_periodo
        ).filter(
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia)
        ).select_related('domain'),
        
        'hostings': HostingCost.objects.filter(
            **filtro_periodo
        ).filter(
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia)
        ).select_related('hosting'),
        
        'vps': VPSCost.objects.filter(
            **filtro_periodo
        ).filter(
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia)
        ).select_related('vps'),
        
        'backups': VPSBackupCost.objects.filter(
            **filtro_periodo
        ).filter(
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia)
        ).select_related('backup__vps'),
        
        'emails': DomainEmailCost.objects.filter(
            **filtro_periodo
        ).filter(
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia)
        ).select_related('email__dominio'),
    }


def _calcular_rateios(contratos, custos_por_tipo, primeiro_dia, ultimo_dia) -> dict:
    """
    Calcula rateio de cada tipo de custo por contrato.
    
    Returns:
        dict: {
            contrato_id: {
                'receita': Decimal,
                'custo_dominios': Decimal,
                'custo_hostings': Decimal,
                'custo_vps': Decimal,
                'custo_backups': Decimal,
                'custo_emails': Decimal,
                'detalhamento': dict
            }
        }
    """
    contratos_list = list(contratos)
    rateios = defaultdict(lambda: {
        'receita': Decimal('0.00'),
        'custo_dominios': Decimal('0.00'),
        'custo_hostings': Decimal('0.00'),
        'custo_vps': Decimal('0.00'),
        'custo_backups': Decimal('0.00'),
        'custo_emails': Decimal('0.00'),
        'custo_despesas_adicionais': Decimal('0.00'),
        'detalhamento': {
            'dominios': [],
            'hostings': [],
            'vps': [],
            'backups': [],
            'emails': [],
            'despesas_adicionais': [],
            'invoices': []
        }
    })
    
    # Receita por contrato via vínculo explícito (InvoiceContrato)
    mes_ref = primeiro_dia.month
    ano_ref = primeiro_dia.year
    
    itens = InvoiceContrato.objects.filter(
        contrato__in=contratos_list,
        invoice__mes_referencia=mes_ref,
        invoice__ano_referencia=ano_ref
    ).select_related('invoice', 'contrato')
    
    itens_por_contrato = defaultdict(list)
    for item in itens:
        itens_por_contrato[item.contrato_id].append(item)
    
    for contrato in contratos_list:
        itens_contrato = itens_por_contrato.get(contrato.id, [])
        
        if itens_contrato:
            receita = sum(i.valor for i in itens_contrato)
            rateios[contrato.id]['receita'] = receita
            
            for item in itens_contrato:
                inv = item.invoice
                rateios[contrato.id]['detalhamento']['invoices'].append({
                    'id': inv.id,
                    'status': inv.status,
                    'valor_invoice': float(inv.valor_total),
                    'valor_contrato': float(item.valor),
                    'vencimento': str(inv.vencimento),
                    'order_nsu': inv.order_nsu or ''
                })
        else:
            # Sem invoice no período: receita 0
            rateios[contrato.id]['receita'] = Decimal('0.00')
            rateios[contrato.id]['detalhamento']['invoices'].append({
                'observacao': 'Sem invoice no período - receita zerada'
            })
    
    # Ratear domínios
    for cost in custos_por_tipo['dominios']:
        contratos_domain = [c for c in contratos_list if cost.domain in c.dominios.all()]
        if contratos_domain:
            custo_mensal = calcular_custo_mensal(cost)
            custo_rateado = ratear_por_contratos(custo_mensal, contratos_domain)
            
            for contrato in contratos_domain:
                rateios[contrato.id]['custo_dominios'] += custo_rateado
                rateios[contrato.id]['detalhamento']['dominios'].append({
                    'nome': cost.domain.nome,
                    'custo': float(custo_rateado),
                    'custo_total': float(custo_mensal),
                    'rateio': len(contratos_domain)
                })
    
    # Ratear hostings
    for cost in custos_por_tipo['hostings']:
        contratos_hosting = [c for c in contratos_list if cost.hosting in c.hostings.all()]
        if contratos_hosting:
            custo_mensal = calcular_custo_mensal(cost)
            custo_rateado = ratear_por_contratos(custo_mensal, contratos_hosting)
            
            for contrato in contratos_hosting:
                rateios[contrato.id]['custo_hostings'] += custo_rateado
                rateios[contrato.id]['detalhamento']['hostings'].append({
                    'nome': cost.hosting.nome,
                    'custo': float(custo_rateado),
                    'custo_total': float(custo_mensal),
                    'rateio': len(contratos_hosting)
                })
    
    # Ratear VPS
    for cost in custos_por_tipo['vps']:
        # VPS usa relacionamento M2M customizado com período
        from infra.vps.models import VPSContrato
        
        vinculos_ativos = VPSContrato.objects.filter(
            vps=cost.vps,
            data_inicio__lt=ultimo_dia
        ).filter(
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia)
        ).select_related('contrato')
        
        contratos_vps = [v.contrato for v in vinculos_ativos if v.contrato in contratos_list]
        
        if contratos_vps:
            custo_mensal = calcular_custo_mensal(cost)
            custo_rateado = ratear_por_contratos(custo_mensal, contratos_vps)
            
            for contrato in contratos_vps:
                rateios[contrato.id]['custo_vps'] += custo_rateado
                rateios[contrato.id]['detalhamento']['vps'].append({
                    'nome': cost.vps.nome,
                    'custo': float(custo_rateado),
                    'custo_total': float(custo_mensal),
                    'rateio': len(contratos_vps)
                })
    
    # Ratear Backups (seguem a VPS)
    for cost in custos_por_tipo['backups']:
        from infra.vps.models import VPSContrato
        
        vinculos_ativos = VPSContrato.objects.filter(
            vps=cost.backup.vps,
            data_inicio__lt=ultimo_dia
        ).filter(
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia)
        ).select_related('contrato')
        
        contratos_backup = [v.contrato for v in vinculos_ativos if v.contrato in contratos_list]
        
        if contratos_backup:
            custo_mensal = calcular_custo_mensal(cost)
            custo_rateado = ratear_por_contratos(custo_mensal, contratos_backup)
            
            for contrato in contratos_backup:
                rateios[contrato.id]['custo_backups'] += custo_rateado
                rateios[contrato.id]['detalhamento']['backups'].append({
                    'nome': cost.backup.nome,
                    'vps': cost.backup.vps.nome,
                    'custo': float(custo_rateado),
                    'custo_total': float(custo_mensal),
                    'rateio': len(contratos_backup)
                })
    
    # Emails (SEM rateio - custo direto do contrato)
    for cost in custos_por_tipo['emails']:
        # Email pertence diretamente a um contrato específico
        if cost.email.contrato in contratos_list:
            contrato = cost.email.contrato
            custo_mensal = calcular_custo_mensal(cost)
            
            rateios[contrato.id]['custo_emails'] += custo_mensal
            rateios[contrato.id]['detalhamento']['emails'].append({
                'dominio': cost.email.dominio.nome,
                'fornecedor': cost.email.fornecedor,
                'custo': float(custo_mensal),
                'custo_total': float(custo_mensal),
                'rateio': 1  # Sem rateio
            })
    
    # Despesas Adicionais (diretas por contrato)
    mes_ref = primeiro_dia.month
    ano_ref = primeiro_dia.year
    
    despesas_adicionais = DespesaAdicional.objects.filter(
        mes_referencia=mes_ref,
        ano_referencia=ano_ref,
        contrato__in=contratos_list
    ).select_related('contrato')
    
    for despesa in despesas_adicionais:
        rateios[despesa.contrato.id]['custo_despesas_adicionais'] += despesa.valor
        rateios[despesa.contrato.id]['detalhamento']['despesas_adicionais'].append({
            'descricao': despesa.descricao,
            'valor': float(despesa.valor),
            'observacoes': despesa.observacoes
        })
    
    return dict(rateios)


def _criar_snapshot(contrato, periodo, rateio_dados) -> ContratoSnapshot:
    """
    Cria um snapshot imutável de um contrato em um período.
    
    Para contratos internos (cliente.tipo == 'interno'):
    - Margem percentual = NULL (não faz sentido calcular sem receita)
    - Usado para controlar custos operacionais próprios
    """
    receita = rateio_dados['receita']
    custo_total = (
        rateio_dados['custo_dominios'] +
        rateio_dados['custo_hostings'] +
        rateio_dados['custo_vps'] +
        rateio_dados['custo_backups'] +
        rateio_dados['custo_emails'] +
        rateio_dados['custo_despesas_adicionais']
    )
    
    margem = receita - custo_total
    
    # Calcular margem percentual
    # Para contratos internos (sem receita real), margem percentual = NULL
    is_interno = contrato.cliente.tipo == 'interno'
    
    if is_interno or receita == 0:
        # Contrato interno ou sem receita: não calcular margem percentual
        margem_percentual = None
    elif receita > 0:
        # Contrato normal: calcular margem percentual com limite
        margem_pct_raw = (margem / receita * 100)
        # Limitar entre -99999.99 e 99999.99 para evitar overflow
        margem_pct_raw = max(Decimal('-99999.99'), min(margem_pct_raw, Decimal('99999.99')))
        margem_percentual = margem_pct_raw.quantize(Decimal('0.01'))
    else:
        margem_percentual = Decimal('0.00')
    
    snapshot = ContratoSnapshot.objects.create(
        contrato=contrato,
        periodo=periodo,
        receita=receita,
        custo_dominios=rateio_dados['custo_dominios'],
        custo_hostings=rateio_dados['custo_hostings'],
        custo_vps=rateio_dados['custo_vps'],
        custo_backups=rateio_dados['custo_backups'],
        custo_emails=rateio_dados['custo_emails'],
        custo_despesas_adicionais=rateio_dados['custo_despesas_adicionais'],
        custo_total=custo_total,
        margem=margem,
        margem_percentual=margem_percentual,
        detalhamento=rateio_dados['detalhamento']
    )
    
    return snapshot
