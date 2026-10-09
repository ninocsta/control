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
    vencimento = models.DateField(help_text='Próxima renovação. Use a ação "Renovar" para avançar o período.')
    pago_pelo_cliente = models.BooleanField(
        default=False,
        help_text='O cliente paga direto ao fornecedor: só controla o vencimento, não entra em custo/margem.'
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def ativo_em(self, primeiro_dia, ultimo_dia):
        """Mesmo critério do fechamento: começou antes do fim do mês e não terminou antes do início."""
        return self.data_inicio < ultimo_dia and (self.data_fim is None or self.data_fim >= primeiro_dia)

    def clean(self):
        from django.core.exceptions import ValidationError
        from infra.financeiro.services.rateio import validar_alteracao_custo
        if self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError({'data_fim': 'Data de fim não pode ser anterior à data de início.'})
        validar_alteracao_custo(self)

    @property
    def custo_mensal(self):
        if not self.periodo_meses:
            return Decimal('0.00')
        return (self.valor_total / Decimal(self.periodo_meses)).quantize(
            Decimal('0.01')
        )
    

    class Meta:
        abstract = True
