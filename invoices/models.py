from django.db import models
from clientes.models import Cliente
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.core.exceptions import ValidationError

# Create your models here.
class Invoice(models.Model):
    """
    Representa a cobrança mensal do cliente.
    
    Regras:
    - 1 invoice por cliente por mês (constraint)
    - Valor = soma dos contratos ativos no mês
    - Despesas NÃO entram aqui (são custos do sistema)
    - Webhook da InfinitePay altera status para pago
    """
    
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('pago', 'Pago'),
        ('atrasado', 'Atrasado'),
        ('cancelado', 'Cancelado'),
    ]
    
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    
    # Referência temporal
    mes_referencia = models.IntegerField(help_text="Mês (1-12)")
    ano_referencia = models.IntegerField(help_text="Ano (ex: 2025)")
    
    # Valores
    valor_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Status e vencimento
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    vencimento = models.DateField()
    
    # InfinitePay Integration
    order_nsu = models.CharField(max_length=100, blank=True, help_text="NSU do pedido InfinitePay")
    invoice_slug = models.CharField(max_length=100, blank=True, unique=True, null=True)
    transaction_nsu = models.CharField(max_length=100, blank=True, help_text="NSU da transação")
    capture_method = models.CharField(max_length=50, blank=True)
    receipt_url = models.URLField(blank=True, help_text="URL do recibo de pagamento")
    
    # Controle temporal
    criado_em = models.DateTimeField(auto_now_add=True)
    pago_em = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        ordering = ['-ano_referencia', '-mes_referencia', '-criado_em']
        # Removida constraint única - permite múltiplos invoices por cliente/mês
        # (invoice mensal + invoices adicionais de horas extras, implementação, etc)
        indexes = [
            models.Index(fields=['mes_referencia', 'ano_referencia']),
            models.Index(fields=['status']),
            models.Index(fields=['vencimento']),
            models.Index(fields=['cliente', 'mes_referencia', 'ano_referencia']),
        ]
    
    def __str__(self):
        return f"Invoice {self.cliente.nome} - {self.mes_referencia:02d}/{self.ano_referencia} - R$ {self.valor_total}"
    
    def clean(self):
        if not 1 <= self.mes_referencia <= 12:
            raise ValidationError('Mês deve estar entre 1 e 12')