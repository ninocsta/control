# infra/backups/models.py
from django.db import models
from infra.core import models as core_models
from infra.vps.models import VPS


class VPSBackup(models.Model):
    """
    Backup associado a uma VPS.
    O custo do backup soma ao custo da VPS no fechamento mensal.
    """

    vps = models.ForeignKey(
        VPS,
        on_delete=models.CASCADE,
        related_name='backups'
    )

    nome = models.CharField(max_length=200)
    fornecedor = models.CharField(max_length=200, blank=True)

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} ({self.vps.nome})"


class VPSBackupCost(core_models.InfraCostModel):
    """
    Histórico de custos do backup.
    """

    backup = models.ForeignKey(
        VPSBackup,
        on_delete=models.PROTECT,
        related_name='costs'
    )

    class Meta:
        ordering = ['-data_inicio']
