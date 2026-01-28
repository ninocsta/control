from django.contrib import admin
from .models import Dominio, DomainCost


class DomainCostInline(admin.TabularInline):
    model = DomainCost
    extra = 0
    fields = (
        'valor_total', 'periodo_meses', 'custo_mensal_calc',
        'data_inicio', 'data_fim', 'vencimento', 'ativo'
    )
    readonly_fields = ('custo_mensal_calc',)
    
    def custo_mensal_calc(self, obj):
        if obj.id:
            return f"R$ {obj.custo_mensal:,.2f}"
        return "—"
    custo_mensal_calc.short_description = 'Custo Mensal'


@admin.register(Dominio)
class DominioAdmin(admin.ModelAdmin):
    list_display = ('nome', 'fornecedor', 'ativo', 'custo_atual', 'criado_em')
    list_filter = ('ativo', 'fornecedor', 'criado_em')
    search_fields = ('nome', 'fornecedor')
    filter_horizontal = ('contratos',)
    inlines = [DomainCostInline]
    
    fieldsets = (
        ('Informações do Domínio', {
            'fields': ('nome', 'fornecedor')
        }),
        ('Contratos Vinculados', {
            'fields': ('contratos',)
        }),
        ('Status', {
            'fields': ('ativo',)
        }),
    )
    
    def custo_atual(self, obj):
        cost = obj.costs.filter(ativo=True).order_by('-data_inicio').first()
        if cost:
            return f"R$ {cost.custo_mensal:,.2f}/mês"
        return "Sem custo"
    custo_atual.short_description = 'Custo Atual'


@admin.register(DomainCost)
class DomainCostAdmin(admin.ModelAdmin):
    list_display = (
        'domain', 'valor_total', 'periodo_meses', 'custo_mensal',
        'data_inicio', 'data_fim', 'vencimento', 'ativo'
    )
    list_filter = ('ativo', 'data_inicio', 'vencimento')
    search_fields = ('domain__nome',)
    
    fieldsets = (
        ('Domínio', {
            'fields': ('domain',)
        }),
        ('Valores', {
            'fields': ('valor_total', 'periodo_meses')
        }),
        ('Período', {
            'fields': ('data_inicio', 'data_fim', 'vencimento')
        }),
        ('Status', {
            'fields': ('ativo',)
        }),
    )
