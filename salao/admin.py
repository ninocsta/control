from django.contrib import admin

from .models import (
    CategoriaDespesaSalao,
    ComissaoMensalSalao,
    DespesaSalao,
    FormaPagamentoSalao,
    LancamentoSalao,
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
    list_display = ('data', 'categoria', 'valor', 'parcela_numero', 'parcelas_total', 'criado_em')
    list_filter = ('data', 'categoria')
    search_fields = ('categoria__nome', 'observacao')
    date_hierarchy = 'data'


@admin.register(ComissaoMensalSalao)
class ComissaoMensalSalaoAdmin(admin.ModelAdmin):
    list_display = ('mes', 'ano', 'percentual', 'valor_pago_override', 'updated_at')
    list_filter = ('ano', 'mes')
    readonly_fields = ('updated_at',)
