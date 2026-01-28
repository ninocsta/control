from django.contrib import admin
from .models import Contrato
from infra.financeiro.models import ContratoSnapshot
from decimal import Decimal


class ContratoSnapshotInline(admin.TabularInline):
    model = ContratoSnapshot
    extra = 0
    can_delete = False
    readonly_fields = (
        'periodo', 'receita', 'custo_total', 'margem', 
        'margem_percentual', 'criado_em'
    )
    fields = readonly_fields
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = (
        'nome', 'cliente', 'valor_mensal', 'data_inicio', 
        'data_fim', 'is_ativo', 'custo_medio'
    )
    list_filter = ('data_inicio', 'data_fim', 'cliente')
    search_fields = ('nome', 'cliente__nome', 'descricao')
    readonly_fields = ('custo_medio', 'margem_media', 'total_snapshots')
    inlines = [ContratoSnapshotInline]
    
    fieldsets = (
        ('Informações do Contrato', {
            'fields': ('cliente', 'nome', 'descricao', 'valor_mensal')
        }),
        ('Período de Vigência', {
            'fields': ('data_inicio', 'data_fim')
        }),
        ('Documentos', {
            'fields': ('arquivo_contrato',),
            'classes': ('collapse',)
        }),
        ('Estatísticas (Readonly)', {
            'fields': ('custo_medio', 'margem_media', 'total_snapshots'),
            'classes': ('collapse',)
        }),
    )
    
    def is_ativo(self, obj):
        """Verifica se o contrato está ativo."""
        from datetime import date
        hoje = date.today()
        if obj.data_fim and obj.data_fim < hoje:
            return False
        return obj.data_inicio <= hoje
    is_ativo.boolean = True
    is_ativo.short_description = 'Ativo'
    
    def custo_medio(self, obj):
        """Calcula custo médio dos snapshots."""
        snapshots = obj.snapshots.all()
        if not snapshots:
            return "Sem dados"
        
        custo_total = sum(s.custo_total for s in snapshots)
        media = custo_total / len(snapshots)
        return f"R$ {media:.2f}"
    custo_medio.short_description = 'Custo Médio'
    
    def margem_media(self, obj):
        """Calcula margem média percentual."""
        snapshots = obj.snapshots.all()
        if not snapshots:
            return "Sem dados"
        
        margem_total = sum(s.margem_percentual for s in snapshots)
        media = margem_total / len(snapshots)
        return f"{media:.1f}%"
    margem_media.short_description = 'Margem Média'
    
    def total_snapshots(self, obj):
        """Total de snapshots criados."""
        return obj.snapshots.count()
    total_snapshots.short_description = 'Total de Períodos'
