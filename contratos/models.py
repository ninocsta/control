from django.db import models
from clientes.models import Cliente
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.core.exceptions import ValidationError

# Create your models here.

class Contrato(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='contratos'
    )
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    valor_mensal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Valor mensal do contrato. Pode ser 0 para contratos internos."
    )
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True, help_text="Data em que o contrato foi extinto")
    arquivo_contrato = models.FileField(upload_to='contratos/', null=True, blank=True)

    class Meta:
        verbose_name = 'Contrato'
        verbose_name_plural = 'Contratos'
        ordering = ['-data_inicio']

    def __str__(self):
        return f"{self.nome} - {self.cliente.nome}"
    
    def clean(self):
        # Validar data de fim
        if self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError('Data de fim não pode ser anterior à data de início')
        
        # Para clientes NÃO internos, valor_mensal deve ser > 0
        if self.cliente and self.cliente.tipo != 'interno' and self.valor_mensal <= 0:
            raise ValidationError(
                'Contratos de clientes não-internos devem ter valor mensal maior que zero.'
            )