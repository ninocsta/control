from django.contrib import admin
from .models import DomainEmail, DomainEmailCost


class DomainEmailCostInline(admin.TabularInline):
    model = DomainEmailCost
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


@admin.register(DomainEmail)
class DomainEmailAdmin(admin.ModelAdmin):
    list_display = (
        'dominio', 'contrato', 'fornecedor', 'quantidade_caixas',
        'ativo', 'custo_atual', 'criado_em'
    )
    list_filter = ('ativo', 'fornecedor', 'criado_em', 'contrato__cliente')
    search_fields = ('dominio__nome', 'fornecedor', 'contrato__nome', 'contrato__cliente__nome')
    inlines = [DomainEmailCostInline]
    autocomplete_fields = ['dominio', 'contrato']
    
    fieldsets = (
        ('Informações do Email', {
            'fields': ('dominio', 'contrato', 'fornecedor', 'quantidade_caixas'),
            'description': 'Email é custo singular do contrato, sem rateio entre contratos.'
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


@admin.register(DomainEmailCost)
class DomainEmailCostAdmin(admin.ModelAdmin):
    list_display = (
        'email', 'valor_total', 'periodo_meses', 'custo_mensal',
        'data_inicio', 'data_fim', 'vencimento', 'ativo'
    )
    list_filter = ('ativo', 'data_inicio', 'vencimento')
    search_fields = ('email__dominio__nome',)
    
    fieldsets = (
        ('Email', {
            'fields': ('email',)
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
