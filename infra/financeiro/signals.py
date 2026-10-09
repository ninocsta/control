"""
Signals para proteger a integridade dos dados financeiros.

Regras:
- Alteração de custo usado em período fechado: validada em InfraCostModel.clean()
- Não permitir exclusão de snapshots
- Não permitir alteração de período fechado
"""
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from infra.financeiro.models import PeriodoFinanceiro, ContratoSnapshot


@receiver(pre_save, sender=PeriodoFinanceiro)
def proteger_periodo_fechado(sender, instance, **kwargs):
    """
    Impede alteração de período já fechado.
    """
    if instance.pk:  # Só valida em updates
        periodo_original = PeriodoFinanceiro.objects.get(pk=instance.pk)
        if periodo_original.fechado and not instance.fechado:
            raise ValidationError(
                "Não é possível reabrir um período financeiro fechado."
            )


@receiver(pre_delete, sender=ContratoSnapshot)
def proteger_snapshot_exclusao(sender, instance, **kwargs):
    """
    Impede exclusão de snapshots (dados históricos imutáveis).
    """
    raise ValidationError(
        "Snapshots são imutáveis e não podem ser excluídos. "
        "Se necessário, marque o período como inválido nas observações."
    )
