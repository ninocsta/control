"""
Signals para proteger a integridade dos dados financeiros.

Regras:
- Não permitir alteração de InfraCost se houver snapshot posterior
- Não permitir exclusão de snapshots
- Não permitir alteração de período fechado
"""
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from infra.financeiro.models import PeriodoFinanceiro, ContratoSnapshot
from infra.dominios.models import DomainCost
from infra.hosting.models import HostingCost
from infra.vps.models import VPSCost
from infra.backups.models import VPSBackupCost
from infra.emails.models import DomainEmailCost


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


def validar_custo_com_snapshot(cost_instance, model_name):
    """
    Valida se um custo pode ser alterado com base em snapshots existentes.
    """
    if not cost_instance.pk:
        return  # Novos custos podem ser criados
    
    # Buscar o custo original
    cost_original = cost_instance.__class__.objects.get(pk=cost_instance.pk)
    
    # Se não mudou nada relevante, permite
    if (cost_original.valor_total == cost_instance.valor_total and
        cost_original.periodo_meses == cost_instance.periodo_meses and
        cost_original.data_inicio == cost_instance.data_inicio and
        cost_original.data_fim == cost_instance.data_fim):
        return
    
    # Verificar se há snapshots posteriores à data_inicio
    from infra.financeiro.models import PeriodoFinanceiro
    from datetime import date
    
    periodos_fechados = PeriodoFinanceiro.objects.filter(
        fechado=True
    )
    
    for periodo in periodos_fechados:
        primeiro_dia_periodo = date(periodo.ano, periodo.mes, 1)
        
        # Se o custo estava ativo nesse período, não pode alterar
        if (cost_instance.data_inicio <= primeiro_dia_periodo and
            (cost_instance.data_fim is None or cost_instance.data_fim >= primeiro_dia_periodo)):
            
            raise ValidationError(
                f"Não é possível alterar este custo pois há períodos fechados "
                f"que dependem dele ({periodo}). Crie um novo registro de custo "
                f"com data_inicio futura."
            )


@receiver(pre_save, sender=DomainCost)
def validar_domain_cost(sender, instance, **kwargs):
    validar_custo_com_snapshot(instance, 'DomainCost')


@receiver(pre_save, sender=HostingCost)
def validar_hosting_cost(sender, instance, **kwargs):
    validar_custo_com_snapshot(instance, 'HostingCost')


@receiver(pre_save, sender=VPSCost)
def validar_vps_cost(sender, instance, **kwargs):
    validar_custo_com_snapshot(instance, 'VPSCost')


@receiver(pre_save, sender=VPSBackupCost)
def validar_backup_cost(sender, instance, **kwargs):
    validar_custo_com_snapshot(instance, 'VPSBackupCost')


@receiver(pre_save, sender=DomainEmailCost)
def validar_email_cost(sender, instance, **kwargs):
    validar_custo_com_snapshot(instance, 'DomainEmailCost')
