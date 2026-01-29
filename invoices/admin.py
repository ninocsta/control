from django.contrib import admin
from django.utils.html import format_html
from .models import Invoice

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'get_invoice_number', 'cliente', 'valor_total_display',
        'vencimento', 'status_badge', 'pago_em', 'order_nsu', 'invoice_slug'
    )
    list_filter = (
        'status', 'ano_referencia', 'mes_referencia', 'cliente',
        'vencimento',
    )
    search_fields = (
        'cliente__nome', 'order_nsu', 'invoice_slug', 'transaction_nsu',
    )
    date_hierarchy = 'vencimento'
    readonly_fields = ('criado_em', 'pago_em')

    fieldsets = (
        ('Cliente e Período', {
            'fields': ('cliente', 'mes_referencia', 'ano_referencia')
        }),
        ('Valores e Status', {
            'fields': ('valor_total', 'vencimento', 'status')
        }),
        ('Integração InfinitePay', {
            'fields': (
                'order_nsu', 'invoice_slug', 'transaction_nsu',
                'capture_method', 'receipt_url'
            ),
            'classes': ('collapse',)
        }),
        ('Controle', {
            'fields': ('criado_em', 'pago_em'),
            'classes': ('collapse',)
        }),
    )

    def get_invoice_number(self, obj):
        return f"{obj.mes_referencia:02d}/{obj.ano_referencia}"
    get_invoice_number.short_description = 'Período'

    def valor_total_display(self, obj):
        return f"R$ {obj.valor_total:,.2f}"
    valor_total_display.short_description = 'Valor'
    valor_total_display.admin_order_field = 'valor_total'

    def status_badge(self, obj):
        colors = {
            'pendente': '#ffc107',
            'pago': '#28a745',
            'atrasado': '#dc3545',
            'cancelado': '#6c757d',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
