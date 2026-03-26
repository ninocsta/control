from django.contrib import admin

from .models import (
    CompraEstoqueItemSalao,
    CompraEstoqueSalao,
    CategoriaDespesaSalao,
    ComissaoMensalSalao,
    DespesaSalao,
    FormaPagamentoSalao,
    LancamentoSalao,
    MovimentoEstoqueSalao,
    ProdutoSalao,
    ServicoSalao,
    TaxaFormaPagamentoSalao,
)


@admin.register(ServicoSalao)
class ServicoSalaoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'valor_padrao', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('codigo', 'nome')
    ordering = ('codigo',)


@admin.register(CategoriaDespesaSalao)
class CategoriaDespesaSalaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome',)
    ordering = ('nome',)


@admin.register(FormaPagamentoSalao)
class FormaPagamentoSalaoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'aceita_parcelamento', 'ativo')
    list_filter = ('aceita_parcelamento', 'ativo')
    search_fields = ('codigo', 'nome')
    ordering = ('codigo',)


@admin.register(TaxaFormaPagamentoSalao)
class TaxaFormaPagamentoSalaoAdmin(admin.ModelAdmin):
    list_display = ('forma_pagamento', 'parcelas', 'percentual')
    list_filter = ('forma_pagamento', 'parcelas')
    search_fields = ('forma_pagamento__codigo', 'forma_pagamento__nome')
    ordering = ('forma_pagamento__codigo', 'parcelas')


@admin.register(LancamentoSalao)
class LancamentoSalaoAdmin(admin.ModelAdmin):
    list_display = ('data', 'servico', 'forma_pagamento', 'parcelas', 'valor_bruto', 'valor_taxa', 'valor_cobrado', 'criado_em')
    list_filter = ('data', 'servico', 'forma_pagamento', 'parcelas')
    search_fields = ('servico__codigo', 'servico__nome', 'forma_pagamento__codigo', 'forma_pagamento__nome')
    date_hierarchy = 'data'


@admin.register(DespesaSalao)
class DespesaSalaoAdmin(admin.ModelAdmin):
    list_display = (
        'data',
        'categoria',
        'gera_estoque',
        'valor',
        'parcela_numero',
        'parcelas_total',
        'criado_em',
    )
    list_filter = ('data', 'categoria', 'gera_estoque')
    search_fields = ('categoria__nome', 'observacao')
    date_hierarchy = 'data'


@admin.register(ComissaoMensalSalao)
class ComissaoMensalSalaoAdmin(admin.ModelAdmin):
    list_display = ('mes', 'ano', 'percentual', 'valor_pago_override', 'updated_at')
    list_filter = ('ano', 'mes')
    readonly_fields = ('updated_at',)


@admin.register(ProdutoSalao)
class ProdutoSalaoAdmin(admin.ModelAdmin):
    list_display = (
        'codigo',
        'nome',
        'unidade',
        'saldo_atual',
        'estoque_minimo',
        'custo_medio_atual',
        'valor_venda_padrao',
        'ativo',
    )
    list_filter = ('ativo',)
    search_fields = ('codigo', 'nome')
    ordering = ('codigo',)


@admin.register(CompraEstoqueSalao)
class CompraEstoqueSalaoAdmin(admin.ModelAdmin):
    list_display = ('data', 'categoria_fornecedor', 'valor_total', 'parcelas_total', 'criado_em')
    list_filter = ('data', 'categoria_fornecedor', 'parcelas_total')
    search_fields = ('categoria_fornecedor__nome', 'observacao')
    date_hierarchy = 'data'


@admin.register(CompraEstoqueItemSalao)
class CompraEstoqueItemSalaoAdmin(admin.ModelAdmin):
    list_display = ('compra', 'produto', 'quantidade', 'custo_unitario', 'custo_total')
    list_filter = ('produto',)
    search_fields = ('produto__codigo', 'produto__nome', 'compra__categoria_fornecedor__nome')


@admin.register(MovimentoEstoqueSalao)
class MovimentoEstoqueSalaoAdmin(admin.ModelAdmin):
    list_display = (
        'data',
        'produto',
        'tipo',
        'motivo',
        'quantidade',
        'valor_liquido_venda',
        'valor_custo_total',
        'lucro_produto',
        'forma_pagamento',
    )
    list_filter = ('data', 'tipo', 'motivo', 'forma_pagamento', 'produto')
    search_fields = ('produto__codigo', 'produto__nome', 'observacao')
    date_hierarchy = 'data'
