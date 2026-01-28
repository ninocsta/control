# infra/hostings/models.py
from infra.core import models as core_models
from django.db import models


class Hosting(core_models.InfraModel):

    def __str__(self):
        return f"{self.nome} ({self.fornecedor})"


class HostingCost(core_models.InfraCostModel):
    hosting = models.ForeignKey(
        Hosting,
        on_delete=models.PROTECT,
        related_name='costs'
    )

    class Meta:
        ordering = ['-data_inicio']
