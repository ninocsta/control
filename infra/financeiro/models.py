# infra/financeiro/models.py
from django.db import models
from django.core.exceptions import ValidationError
from contratos.models import Contrato
from decimal import Decimal


class PeriodoFinanceiro(models.Model):
    mes = models.PositiveSmallIntegerField()
    ano = models.PositiveSmallIntegerField()

    fechado = models.BooleanField(default=False)
    fechado_em = models.DateTimeField(null=True, blank=True)
    fechado_por = models.CharField(max_length=200, blank=True)

    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ano', '-mes']
        constraints = [
            models.UniqueConstraint(
                fields=['mes', 'ano'],
                name='unique_periodo_financeiro'
            )
        ]

    def __str__(self):
        status = "Fechado" if self.fechado else "Aberto"
        return f"{self.mes:02d}/{self.ano} ({status})"

    def clean(self):
        if not 1 <= self.mes <= 12:
            raise ValidationError('Mês deve estar entre 1 e 12')




class ContratoSnapshot(models.Model):
    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.PROTECT,
        related_name='snapshots'
    )

    periodo = models.ForeignKey(
        PeriodoFinanceiro,
        on_delete=models.PROTECT,
        related_name='contrato_snapshots'
    )

    receita = models.DecimalField(max_digits=10, decimal_places=2)

    custo_dominios = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    custo_hostings = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    custo_vps = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    custo_backups = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    custo_emails = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    custo_total = models.DecimalField(max_digits=10, decimal_places=2)
    margem = models.DecimalField(max_digits=10, decimal_places=2)
    margem_percentual = models.DecimalField(max_digits=5, decimal_places=2)

    detalhamento = models.JSONField(default=dict)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-periodo__ano', '-periodo__mes']
        constraints = [
            models.UniqueConstraint(
                fields=['contrato', 'periodo'],
                name='unique_contrato_snapshot'
            )
        ]

    def __str__(self):
        return f"{self.contrato} - {self.periodo}"
