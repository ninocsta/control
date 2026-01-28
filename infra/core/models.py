from django.db import models
from contratos.models import Contrato
from django.core.validators import MinValueValidator
from decimal import Decimal


class InfraModel(models.Model):
    nome = models.CharField(max_length=200)
    fornecedor = models.CharField(max_length=200)

    contratos = models.ManyToManyField(
        Contrato,
        related_name='%(class)ss',
        blank=True
    )

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    

    class Meta:
        abstract = True


class InfraCostModel(models.Model):
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    periodo_meses = models.IntegerField(
        validators=[MinValueValidator(1)]
    )    
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    vencimento = models.DateField()
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    @property
    def custo_mensal(self):
        if not self.periodo_meses:
            return Decimal('0.00')
        return (self.valor_total / Decimal(self.periodo_meses)).quantize(
            Decimal('0.01')
        )
    

    class Meta:
        abstract = True
