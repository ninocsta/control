# infra/vps/models.py
from django.db import models
from contratos.models import Contrato
from infra.core import models as core_models


class VPS(models.Model):
    nome = models.CharField(max_length=200)
    fornecedor = models.CharField(max_length=200)

    contratos = models.ManyToManyField(
        Contrato,
        through='VPSContrato',
        related_name='vps_list'
    )

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} ({self.fornecedor})"


class VPSContrato(models.Model):
    vps = models.ForeignKey(VPS, on_delete=models.CASCADE)
    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE)

    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        unique_together = ['vps', 'contrato']

    def __str__(self):
        return f"{self.vps} → {self.contrato}"


class VPSCost(core_models.InfraCostModel):
    vps = models.ForeignKey(
        VPS,
        on_delete=models.PROTECT,
        related_name='costs'
    )

    class Meta:
        ordering = ['-data_inicio']
