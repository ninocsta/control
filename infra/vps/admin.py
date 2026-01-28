from django.contrib import admin
from .models import VPS, VPSCost, VPSContrato


class VPSCostInline(admin.TabularInline):
    model = VPSCost
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


class VPSContratoInline(admin.TabularInline):
    model = VPSContrato
    extra = 0
    fields = ('contrato', 'data_inicio', 'data_fim', 'ativo')


@admin.register(VPS)
class VPSAdmin(admin.ModelAdmin):
    list_display = ('nome', 'fornecedor', 'ativo', 'custo_atual', 'criado_em')
    list_filter = ('ativo', 'fornecedor', 'criado_em')
    search_fields = ('nome', 'fornecedor')
    inlines = [VPSContratoInline, VPSCostInline]
    
    fieldsets = (
        ('Informações do VPS', {
            'fields': ('nome', 'fornecedor')
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


@admin.register(VPSCost)
class VPSCostAdmin(admin.ModelAdmin):
    list_display = (
        'vps', 'valor_total', 'periodo_meses', 'custo_mensal',
        'data_inicio', 'data_fim', 'vencimento', 'ativo'
    )
    list_filter = ('ativo', 'data_inicio', 'vencimento')
    search_fields = ('vps__nome',)
    
    fieldsets = (
        ('VPS', {
            'fields': ('vps',)
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


@admin.register(VPSContrato)
class VPSContratoAdmin(admin.ModelAdmin):
    list_display = ('vps', 'contrato', 'data_inicio', 'data_fim', 'ativo')
    list_filter = ('ativo', 'data_inicio')
    search_fields = ('vps__nome', 'contrato__nome')
