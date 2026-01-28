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
