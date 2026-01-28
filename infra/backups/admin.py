from django.contrib import admin
from .models import VPSBackup, VPSBackupCost


class VPSBackupCostInline(admin.TabularInline):
    model = VPSBackupCost
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


@admin.register(VPSBackup)
class VPSBackupAdmin(admin.ModelAdmin):
    list_display = ('nome', 'vps', 'fornecedor', 'ativo', 'custo_atual', 'criado_em')
    list_filter = ('ativo', 'fornecedor', 'criado_em')
    search_fields = ('nome', 'vps__nome', 'fornecedor')
    inlines = [VPSBackupCostInline]
    
    fieldsets = (
        ('Informações do Backup', {
            'fields': ('nome', 'vps', 'fornecedor')
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


@admin.register(VPSBackupCost)
class VPSBackupCostAdmin(admin.ModelAdmin):
    list_display = (
        'backup', 'valor_total', 'periodo_meses', 'custo_mensal',
        'data_inicio', 'data_fim', 'vencimento', 'ativo'
    )
    list_filter = ('ativo', 'data_inicio', 'vencimento')
    search_fields = ('backup__nome', 'backup__vps__nome')
    
    fieldsets = (
        ('Backup', {
            'fields': ('backup',)
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
