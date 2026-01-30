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


class DespesaAdicional(models.Model):
    """
    Despesas adicionais/excepcionais vinculadas a contratos.
    
    Exemplos:
    - Custos de implementação
    - Suporte técnico extra
    - Compra de licenças
    - Qualquer despesa que não se encaixa nas categorias padrão
    """
    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.PROTECT,
        related_name='despesas_adicionais'
    )
    
    descricao = models.CharField(
        max_length=200,
        help_text="Descrição da despesa (ex: 'Licença Office 365', 'Suporte emergencial')"
    )
    
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Valor da despesa"
    )
    
    mes_referencia = models.PositiveSmallIntegerField(
        help_text="Mês em que a despesa deve ser contabilizada (1-12)"
    )
    ano_referencia = models.PositiveSmallIntegerField(
        help_text="Ano da despesa (ex: 2025)"
    )
    
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.CharField(max_length=200, blank=True)
    
    class Meta:
        verbose_name = 'Despesa Adicional'
        verbose_name_plural = 'Despesas Adicionais'
        ordering = ['-ano_referencia', '-mes_referencia', '-criado_em']
        indexes = [
            models.Index(fields=['mes_referencia', 'ano_referencia']),
            models.Index(fields=['contrato']),
        ]
    
    def __str__(self):
        return f"{self.descricao} - R$ {self.valor} ({self.mes_referencia:02d}/{self.ano_referencia})"
    
    def clean(self):
        if not 1 <= self.mes_referencia <= 12:
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

    receita = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Receita REAL do período (soma de invoices pagos)"
    )

    custo_dominios = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    custo_hostings = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    custo_vps = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    custo_backups = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    custo_emails = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    custo_despesas_adicionais = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Despesas adicionais/excepcionais do período"
    )

    custo_total = models.DecimalField(max_digits=10, decimal_places=2)
    margem = models.DecimalField(max_digits=10, decimal_places=2)
    margem_percentual = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Margem percentual. NULL para contratos internos (sem receita)"
    )

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
