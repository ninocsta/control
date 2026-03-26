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


class ProdutoSalao(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=140)
    unidade = models.CharField(max_length=20, default='UN')
    valor_venda_padrao = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    estoque_minimo = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))],
    )
    saldo_atual = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))],
    )
    custo_medio_atual = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Produto do Salão'
        verbose_name_plural = 'Produtos do Salão'
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or '').strip().upper()
        self.unidade = (self.unidade or '').strip().upper() or 'UN'
        super().save(*args, **kwargs)


class CompraEstoqueSalao(models.Model):
    data = models.DateField(db_index=True)
    categoria_fornecedor = models.ForeignKey(
        CategoriaDespesaSalao,
        on_delete=models.PROTECT,
        related_name='compras_estoque',
    )
    valor_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    parcelas_total = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    grupo_parcelamento_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Compra de Estoque do Salão'
        verbose_name_plural = 'Compras de Estoque do Salão'
        ordering = ['-data', '-id']

    def __str__(self):
        return f"{self.data} - {self.categoria_fornecedor.nome} - R$ {self.valor_total}"


class CompraEstoqueItemSalao(models.Model):
    compra = models.ForeignKey(
        CompraEstoqueSalao,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    produto = models.ForeignKey(
        ProdutoSalao,
        on_delete=models.PROTECT,
        related_name='itens_compra',
    )
    quantidade = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    custo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    custo_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    class Meta:
        verbose_name = 'Item de Compra de Estoque do Salão'
        verbose_name_plural = 'Itens de Compra de Estoque do Salão'
        ordering = ['compra_id', 'id']

    def __str__(self):
        return f"{self.produto.codigo} - {self.quantidade} x R$ {self.custo_unitario}"


class DespesaSalao(models.Model):
    data = models.DateField(db_index=True)
    categoria = models.ForeignKey(
        CategoriaDespesaSalao,
        on_delete=models.PROTECT,
        related_name='despesas',
    )
    gera_estoque = models.BooleanField(default=False)
    compra_estoque = models.ForeignKey(
        CompraEstoqueSalao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='despesas_financeiras',
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


class MovimentoEstoqueSalao(models.Model):
    TIPO_ENTRADA = 'ENTRADA'
    TIPO_SAIDA = 'SAIDA'
    TIPO_CHOICES = (
        (TIPO_ENTRADA, 'Entrada'),
        (TIPO_SAIDA, 'Saída'),
    )

    MOTIVO_COMPRA = 'COMPRA'
    MOTIVO_VENDA = 'VENDA'
    MOTIVO_USO_EM_CLIENTE = 'USO_EM_CLIENTE'
    MOTIVO_AJUSTE = 'AJUSTE'
    MOTIVO_CHOICES = (
        (MOTIVO_COMPRA, 'Compra'),
        (MOTIVO_VENDA, 'Venda'),
        (MOTIVO_USO_EM_CLIENTE, 'Uso em Cliente'),
        (MOTIVO_AJUSTE, 'Ajuste'),
    )

    data = models.DateField(db_index=True)
    produto = models.ForeignKey(
        ProdutoSalao,
        on_delete=models.PROTECT,
        related_name='movimentos',
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    motivo = models.CharField(max_length=20, choices=MOTIVO_CHOICES)
    quantidade = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    custo_unitario_aplicado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    valor_custo_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    valor_venda_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    valor_bruto_venda = models.DecimalField(
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
    valor_liquido_venda = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    lucro_produto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    forma_pagamento = models.ForeignKey(
        FormaPagamentoSalao,
        on_delete=models.PROTECT,
        related_name='movimentos_estoque',
        null=True,
        blank=True,
    )
    parcelas = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    compra_estoque = models.ForeignKey(
        CompraEstoqueSalao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentos_entrada',
    )
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimento de Estoque do Salão'
        verbose_name_plural = 'Movimentos de Estoque do Salão'
        ordering = ['-data', '-id']

    def __str__(self):
        return f"{self.data} - {self.produto.codigo} - {self.tipo} - {self.quantidade}"


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
