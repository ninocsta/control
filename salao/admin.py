from django.contrib import admin

from .models import (
    CategoriaDespesaSalao,
    ComissaoMensalSalao,
    DespesaSalao,
    LancamentoSalao,
    ServicoSalao,
)


@admin.register(ServicoSalao)
class ServicoSalaoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'valor_padrao', 'ativo', 'ordem')
    list_filter = ('ativo',)
    search_fields = ('codigo', 'nome')
    ordering = ('ordem', 'codigo')


@admin.register(CategoriaDespesaSalao)
class CategoriaDespesaSalaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo', 'ordem')
    list_filter = ('ativo',)
    search_fields = ('nome',)
    ordering = ('ordem', 'nome')


@admin.register(LancamentoSalao)
class LancamentoSalaoAdmin(admin.ModelAdmin):
    list_display = ('data', 'servico', 'valor_cobrado', 'criado_em')
    list_filter = ('data', 'servico')
    search_fields = ('servico__codigo', 'servico__nome')
    date_hierarchy = 'data'


@admin.register(DespesaSalao)
class DespesaSalaoAdmin(admin.ModelAdmin):
    list_display = ('data', 'categoria', 'valor', 'criado_em')
    list_filter = ('data', 'categoria')
    search_fields = ('categoria__nome', 'observacao')
    date_hierarchy = 'data'


@admin.register(ComissaoMensalSalao)
class ComissaoMensalSalaoAdmin(admin.ModelAdmin):
    list_display = ('mes', 'ano', 'percentual', 'valor_pago_override', 'updated_at')
    list_filter = ('ano', 'mes')
    readonly_fields = ('updated_at',)
