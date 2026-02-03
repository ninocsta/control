from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import PeriodoFinanceiro, ContratoSnapshot, DespesaAdicional
from .services import fechar_periodo


# Customizar o título do admin
admin.site.site_header = 'Controle Financeiro - Admin'
admin.site.site_title = 'Controle Financeiro'
admin.site.index_title = 'Painel de Administração'


@admin.register(DespesaAdicional)
class DespesaAdicionalAdmin(admin.ModelAdmin):
    list_display = (
        'descricao', 'contrato', 'valor', 'mes_ano_referencia',
        'criado_em', 'criado_por'
    )
    list_filter = ('ano_referencia', 'mes_referencia', 'contrato__cliente')
    search_fields = ('descricao', 'contrato__nome', 'contrato__cliente__nome', 'observacoes')
    readonly_fields = ('criado_em',)
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('contrato', 'descricao', 'valor')
        }),
        ('Período de Referência', {
            'fields': ('mes_referencia', 'ano_referencia')
        }),
        ('Detalhes', {
            'fields': ('observacoes', 'criado_por', 'criado_em'),
            'classes': ('collapse',)
        }),
    )
    
    def mes_ano_referencia(self, obj):
        return f"{obj.mes_referencia:02d}/{obj.ano_referencia}"
    mes_ano_referencia.short_description = 'Período'
    mes_ano_referencia.admin_order_field = 'ano_referencia'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Apenas na criação
            obj.criado_por = request.user.username or request.user.email
        super().save_model(request, obj, form, change)


class ContratoSnapshotInline(admin.TabularInline):
    model = ContratoSnapshot
    extra = 0
    can_delete = False
    readonly_fields = (
        'contrato', 'receita', 'custo_dominios', 'custo_hostings',
        'custo_vps', 'custo_backups', 'custo_emails', 'custo_despesas_adicionais', 'custo_total',
        'margem', 'margem_percentual', 'criado_em'
    )
    fields = readonly_fields
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PeriodoFinanceiro)
class PeriodoFinanceiroAdmin(admin.ModelAdmin):
    list_display = (
        'get_periodo', 'status_badge', 'total_contratos',
        'receita_total', 'custo_total', 'margem_total',
        'fechado_em', 'acoes'
    )
    list_filter = ('fechado', 'ano', 'mes')
    search_fields = ('observacoes',)
    readonly_fields = (
        'fechado', 'fechado_em', 'fechado_por',
        'total_contratos', 'receita_total', 'custo_total',
        'margem_total', 'margem_percentual'
    )
    inlines = [ContratoSnapshotInline]
    
    fieldsets = (
        ('Período', {
            'fields': ('mes', 'ano')
        }),
        ('Status de Fechamento', {
            'fields': ('fechado', 'fechado_em', 'fechado_por')
        }),
        ('Estatísticas', {
            'fields': (
                'total_contratos', 'receita_total', 'custo_total',
                'margem_total', 'margem_percentual'
            ),
            'classes': ('collapse',)
        }),
        ('Observações', {
            'fields': ('observacoes',),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Bloquear edição se período estiver fechado."""
        if obj and obj.fechado:
            campos_modelo = [f.name for f in self.model._meta.fields]
            return list(dict.fromkeys(campos_modelo + list(self.readonly_fields)))
        return self.readonly_fields
    
    def get_periodo(self, obj):
        return f"{obj.mes:02d}/{obj.ano}"
    get_periodo.short_description = 'Período'
    get_periodo.admin_order_field = '-ano'
    
    def status_badge(self, obj):
        if obj.fechado:
            return format_html(
                '<span style="color: white; background-color: green; '
                'padding: 3px 10px; border-radius: 3px;">✓ Fechado</span>'
            )
        else:
            return format_html(
                '<span style="color: white; background-color: orange; '
                'padding: 3px 10px; border-radius: 3px;">⏳ Aberto</span>'
            )
    status_badge.short_description = 'Status'
    
    def total_contratos(self, obj):
        return obj.contrato_snapshots.count()
    total_contratos.short_description = 'Contratos'
    
    def receita_total(self, obj):
        total = sum(s.receita for s in obj.contrato_snapshots.all())
        return f"R$ {total:,.2f}"
    receita_total.short_description = 'Receita Total'
    
    def custo_total(self, obj):
        total = sum(s.custo_total for s in obj.contrato_snapshots.all())
        return f"R$ {total:,.2f}"
    custo_total.short_description = 'Custo Total'
    
    def margem_total(self, obj):
        total = sum(s.margem for s in obj.contrato_snapshots.all())
        return f"R$ {total:,.2f}"
    margem_total.short_description = 'Margem Total'
    
    def margem_percentual(self, obj):
        from decimal import Decimal
        snapshots = obj.contrato_snapshots.all()
        if not snapshots:
            return "N/A"
        
        receita = sum(s.receita for s in snapshots)
        margem = sum(s.margem for s in snapshots)
        
        if receita > 0:
            percentual = (margem / receita * 100)
            return f"{percentual:.1f}%"
        return "0%"
    margem_percentual.short_description = 'Margem %'
    
    def acoes(self, obj):
        if not obj.fechado:
            url = reverse('admin:fechar_periodo', args=[obj.id])
            return format_html(
                '<a class="button" href="{}" style="background-color: #417690; '
                'color: white; padding: 5px 10px; text-decoration: none; '
                'border-radius: 3px;">🔒 Fechar Período</a>',
                url
            )
        return "—"
    acoes.short_description = 'Ações'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:periodo_id>/fechar/',
                self.admin_site.admin_view(self.fechar_periodo_view),
                name='fechar_periodo'
            ),
        ]
        return custom_urls + urls
    
    def fechar_periodo_view(self, request, periodo_id):
        """View customizada para fechar período."""
        try:
            usuario = request.user.get_full_name() or request.user.username
            resultado = fechar_periodo(periodo_id, usuario)
            
            messages.success(
                request,
                f"Período fechado com sucesso! "
                f"Processados {resultado['contratos_processados']} contratos. "
                f"Receita: R$ {resultado['receita_total']:,.2f} | "
                f"Custo: R$ {resultado['custo_total']:,.2f} | "
                f"Margem: R$ {resultado['margem_total']:,.2f}"
            )
        except ValidationError as e:
            messages.error(request, f"Erro ao fechar período: {e}")
        except Exception as e:
            messages.error(request, f"Erro inesperado: {e}")
        
        return redirect('admin:financeiro_periodofinanceiro_changelist')


@admin.register(ContratoSnapshot)
class ContratoSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'contrato', 'periodo', 'receita', 'custo_total',
        'margem', 'margem_percentual_display', 'criado_em'
    )
    list_filter = ('periodo__ano', 'periodo__mes', 'contrato__cliente__tipo', 'contrato__cliente')
    search_fields = ('contrato__nome', 'contrato__cliente__nome')
    readonly_fields = [f.name for f in ContratoSnapshot._meta.fields]
    
    def margem_percentual_display(self, obj):
        """Exibe margem percentual ou 'Interno' para contratos internos."""
        if obj.margem_percentual is None:
            return "Interno"
        return f"{obj.margem_percentual:.2f}%"
    margem_percentual_display.short_description = 'Margem %'
    margem_percentual_display.admin_order_field = 'margem_percentual'
    
    fieldsets = (
        ('Referência', {
            'fields': ('contrato', 'periodo', 'criado_em')
        }),
        ('Valores', {
            'fields': ('receita',)
        }),
        ('Custos Detalhados', {
            'fields': (
                'custo_dominios', 'custo_hostings', 'custo_vps',
                'custo_backups', 'custo_emails', 'custo_total'
            )
        }),
        ('Resultado', {
            'fields': ('margem', 'margem_percentual')
        }),
        ('Detalhamento (JSON)', {
            'fields': ('detalhamento',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Snapshots só podem ser criados via fechamento."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Snapshots são imutáveis."""
        return False
