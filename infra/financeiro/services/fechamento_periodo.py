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
from infra.recursos.models import CustoRecurso
from .rateio import calcular_custo_mensal, ratear_por_contratos, validar_periodo, primeiro_e_proximo_mes


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
        primeiro_dia, ultimo_dia = primeiro_e_proximo_mes(periodo.mes, periodo.ano)
        
        # 3. Buscar contratos ativos no período
        contratos_ativos = Contrato.objects.filter(
            data_inicio__lt=ultimo_dia
        ).filter(
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia)
        ).select_related('cliente')
        
        if not contratos_ativos.exists():
            raise ValidationError(
                f"Nenhum contrato ativo encontrado para o período {periodo}"
            )
        
        # 4. Coletar todos os custos ativos no período
        custos = _coletar_custos_periodo(primeiro_dia, ultimo_dia)
        
        # 5. Calcular rateio por contrato
        rateios_por_contrato = _calcular_rateios(
            contratos_ativos,
            custos,
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


CATEGORIA_POR_TIPO = {
    'dominio': 'dominios',
    'hosting': 'hostings',
    'vps': 'vps',
    'backup': 'backups',
    'email': 'emails',
    'outro': 'outros',
}


def _coletar_custos_periodo(primeiro_dia: date, ultimo_dia: date):
    """Custos de recursos ativos no período (os pagos pelo cliente ficam fora: só controle de vencimento)."""
    return CustoRecurso.objects.filter(
        data_inicio__lt=ultimo_dia,
        ativo=True,
        pago_pelo_cliente=False,
    ).filter(
        models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia)
    ).select_related('recurso', 'recurso__pai')


def _calcular_rateios(contratos, custos, primeiro_dia, ultimo_dia) -> dict:
    """
    Receita (InvoiceContrato do mês, sem canceladas) e custo de cada contrato.
    Custo de recurso: dividido igualmente entre os contratos vinculados no período
    (recurso sem vínculo próprio, como backup, segue os do pai).
    """
    contratos_list = list(contratos)
    ids_ativos = {c.id for c in contratos_list}
    rateios = defaultdict(lambda: {
        'receita': Decimal('0.00'),
        **{f'custo_{cat}': Decimal('0.00') for cat in CATEGORIA_POR_TIPO.values()},
        'custo_despesas_adicionais': Decimal('0.00'),
        'detalhamento': {
            **{cat: [] for cat in CATEGORIA_POR_TIPO.values()},
            'despesas_adicionais': [],
            'invoices': [],
        }
    })

    # Receita por contrato via vínculo explícito (InvoiceContrato)
    mes_ref = primeiro_dia.month
    ano_ref = primeiro_dia.year
    
    itens = InvoiceContrato.objects.filter(
        contrato__in=contratos_list,
        invoice__mes_referencia=mes_ref,
        invoice__ano_referencia=ano_ref
    ).exclude(invoice__status='cancelado').select_related('invoice', 'contrato')
    
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
    
    for cost in custos:
        contrato_ids = sorted({
            v.contrato_id for v in cost.recurso.vinculos_em(primeiro_dia, ultimo_dia)
        } & ids_ativos)
        if not contrato_ids:
            continue
        categoria = CATEGORIA_POR_TIPO[cost.recurso.tipo]
        custo_mensal = calcular_custo_mensal(cost)
        custo_rateado = ratear_por_contratos(custo_mensal, contrato_ids)
        for contrato_id in contrato_ids:
            rateios[contrato_id][f'custo_{categoria}'] += custo_rateado
            rateios[contrato_id]['detalhamento'][categoria].append({
                'nome': cost.recurso.nome,
                'fornecedor': cost.recurso.fornecedor,
                'custo': float(custo_rateado),
                'custo_total': float(custo_mensal),
                'rateio': len(contrato_ids),
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
        rateio_dados['custo_outros'] +
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
        custo_outros=rateio_dados['custo_outros'],
        custo_despesas_adicionais=rateio_dados['custo_despesas_adicionais'],
        custo_total=custo_total,
        margem=margem,
        margem_percentual=margem_percentual,
        detalhamento=rateio_dados['detalhamento']
    )
    
    return snapshot
