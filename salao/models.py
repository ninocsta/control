from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ServicoSalao(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=120)
    valor_padrao = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Serviço do Salão'
        verbose_name_plural = 'Serviços do Salão'
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or '').strip().upper()
        super().save(*args, **kwargs)


class FormaPagamentoSalao(models.Model):
    codigo = models.CharField(max_length=10, unique=True)
    nome = models.CharField(max_length=80)
    ativo = models.BooleanField(default=True)
    aceita_parcelamento = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Forma de Pagamento do Salão'
        verbose_name_plural = 'Formas de Pagamento do Salão'
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or '').strip().upper()
        super().save(*args, **kwargs)


class TaxaFormaPagamentoSalao(models.Model):
    forma_pagamento = models.ForeignKey(
        FormaPagamentoSalao,
        on_delete=models.CASCADE,
        related_name='taxas',
    )
    parcelas = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
    )

    class Meta:
        verbose_name = 'Taxa da Forma de Pagamento do Salão'
        verbose_name_plural = 'Taxas da Forma de Pagamento do Salão'
        ordering = ['forma_pagamento__codigo', 'parcelas']
        constraints = [
            models.UniqueConstraint(
                fields=['forma_pagamento', 'parcelas'],
                name='unique_taxa_forma_pagamento_parcelas_salao',
            )
        ]

    def __str__(self):
        return f"{self.forma_pagamento.codigo} - {self.parcelas}x - {self.percentual}%"


class LancamentoSalao(models.Model):
    data = models.DateField(db_index=True)
    servico = models.ForeignKey(
        ServicoSalao,
        on_delete=models.PROTECT,
        related_name='lancamentos',
    )
    forma_pagamento = models.ForeignKey(
        FormaPagamentoSalao,
        on_delete=models.PROTECT,
        related_name='lancamentos',
        null=True,
        blank=True,
    )
    parcelas = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    valor_bruto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    taxa_percentual_aplicada = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
    )
    valor_taxa = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    valor_cobrado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lançamento do Salão'
        verbose_name_plural = 'Lançamentos do Salão'
        ordering = ['-data', '-id']

    def __str__(self):
        return f"{self.data} - {self.servico.codigo} - R$ {self.valor_cobrado}"


class CategoriaDespesaSalao(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Categoria de Despesa do Salão'
        verbose_name_plural = 'Categorias de Despesa do Salão'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class DespesaSalao(models.Model):
    data = models.DateField(db_index=True)
    categoria = models.ForeignKey(
        CategoriaDespesaSalao,
        on_delete=models.PROTECT,
        related_name='despesas',
    )
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    grupo_parcelamento_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )
    parcela_numero = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    parcelas_total = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Despesa do Salão'
        verbose_name_plural = 'Despesas do Salão'
        ordering = ['-data', '-id']

    def __str__(self):
        return f"{self.data} - {self.categoria.nome} - R$ {self.valor}"


class ComissaoMensalSalao(models.Model):
    ano = models.PositiveSmallIntegerField()
    mes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('20.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
    )
    valor_pago_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    meta_faturamento = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Comissão Mensal do Salão'
        verbose_name_plural = 'Comissões Mensais do Salão'
        ordering = ['-ano', '-mes']
        constraints = [
            models.UniqueConstraint(fields=['ano', 'mes'], name='unique_comissao_mensal_salao')
        ]

    def __str__(self):
        return f"{self.mes:02d}/{self.ano} - {self.percentual}%"
