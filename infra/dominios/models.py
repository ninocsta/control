# infra/domains/models.py
from infra.core import models as core_models
from django.db import models


class Dominio(core_models.InfraModel):

    def __str__(self):
        return self.nome


class DomainCost(core_models.InfraCostModel):
    domain = models.ForeignKey(
        Dominio,
        on_delete=models.PROTECT,
        related_name='costs'
    )

    class Meta:
        ordering = ['-data_inicio']
