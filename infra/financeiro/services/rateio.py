"""
Services de rateio de custos.

Funções puras e reutilizáveis para cálculo de custos mensais
e rateio proporcional entre contratos.
"""
from decimal import Decimal
from typing import List
from django.core.exceptions import ValidationError
from infra.financeiro.models import PeriodoFinanceiro


def calcular_custo_mensal(cost_object) -> Decimal:
    """
    Calcula o custo mensal de um objeto InfraCostModel.
    
    Args:
        cost_object: Instância de DomainCost, HostingCost, VPSCost, etc.
    
    Returns:
        Decimal: Custo mensal calculado
    """
    if not cost_object.periodo_meses:
        return Decimal('0.00')
    
    custo = (cost_object.valor_total / Decimal(cost_object.periodo_meses))
    return custo.quantize(Decimal('0.01'))


def ratear_por_contratos(valor: Decimal, contratos: List) -> Decimal:
    """
    Divide um valor igualmente entre N contratos.
    
    Args:
        valor: Valor total a ser rateado
        contratos: Lista de contratos ativos
    
    Returns:
        Decimal: Valor por contrato (arredondado)
    """
    if not contratos or len(contratos) == 0:
        return Decimal('0.00')
    
    valor_rateado = valor / Decimal(len(contratos))
    return valor_rateado.quantize(Decimal('0.01'))


def validar_periodo(periodo: PeriodoFinanceiro) -> None:
    """
    Valida se um período pode ser fechado.
    
    Args:
        periodo: Instância de PeriodoFinanceiro
    
    Raises:
        ValidationError: Se o período já estiver fechado
    """
    if periodo.fechado:
        raise ValidationError(
            f"Período {periodo} já está fechado desde {periodo.fechado_em}"
        )


def primeiro_e_proximo_mes(mes: int, ano: int):
    """(1º dia do mês, 1º dia do mês seguinte)."""
    from datetime import date
    primeiro = date(ano, mes, 1)
    proximo = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
    return primeiro, proximo


def _periodos_fechados_cobertos(cost) -> set:
    return {
        p.pk for p in PeriodoFinanceiro.objects.filter(fechado=True)
        if cost.ativo_em(*primeiro_e_proximo_mes(p.mes, p.ano))
    }


def validar_alteracao_custo(cost) -> None:
    """
    Custo usado em período fechado não pode mudar de um jeito que altere aquele período.
    Encerrar (data_fim) depois dos períodos fechados, desativar ou mudar o vencimento continua livre.
    """
    if not cost.pk:
        return
    original = cost.__class__.objects.get(pk=cost.pk)
    cobertos_antes = _periodos_fechados_cobertos(original)
    cobertos_depois = _periodos_fechados_cobertos(cost)
    if not (cobertos_antes or cobertos_depois):
        return

    campos_valor = ('valor_total', 'periodo_meses', 'pago_pelo_cliente')
    if any(getattr(original, c) != getattr(cost, c) for c in campos_valor) or cobertos_antes != cobertos_depois:
        raise ValidationError(
            'Este custo já entrou em período financeiro fechado. Para mudar valor/período, '
            'encerre este registro (data de fim após o último período fechado) e crie um novo.'
        )
