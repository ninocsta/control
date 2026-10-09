from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from .models import CustoRecurso


def custos_monitorados(ate=None):
    """
    Custos vigentes com vencimento a acompanhar (renovação), do mais próximo ao mais distante.
    Se o recurso tem custo mais novo, o antigo não conta (registro substituído e não encerrado).
    """
    hoje = timezone.localdate()
    mais_novo = CustoRecurso.objects.filter(
        recurso=OuterRef('recurso'), ativo=True, data_inicio__gt=OuterRef('data_inicio'),
    )
    qs = CustoRecurso.objects.filter(ativo=True, recurso__ativo=True).filter(
        Q(data_fim__isnull=True) | Q(data_fim__gte=hoje)
    ).exclude(Exists(mais_novo)).select_related('recurso', 'recurso__pai').order_by('vencimento')
    if ate:
        qs = qs.filter(vencimento__lte=ate)
    return qs


def renovar(custo):
    """Avança o vencimento em `periodo_meses` (pagou a renovação)."""
    from infra.core.admin import somar_meses
    custo.vencimento = somar_meses(custo.vencimento, custo.periodo_meses)
    custo.save(update_fields=['vencimento'])
    return custo
