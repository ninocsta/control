from django.contrib import admin
from django.forms import BaseInlineFormSet
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from .models import Invoice, InvoiceContrato, MessageQueue


class InvoiceContratoInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        count = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                count += 1
        if count == 0:
            raise ValidationError('Informe ao menos um contrato vinculado ao invoice.')


class InvoiceContratoInline(admin.TabularInline):
    model = InvoiceContrato
    formset = InvoiceContratoInlineFormSet
    extra = 0
    autocomplete_fields = ('contrato',)
    fields = ('contrato', 'valor', 'criado_em')
    readonly_fields = ('criado_em',)

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'get_invoice_number', 'cliente', 'contrato_vinculado', 'valor_total_display',
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
    inlines = (InvoiceContratoInline,)

    fieldsets = (
        ('Cliente e Período', {
            'fields': ('cliente', 'mes_referencia', 'ano_referencia', 'descricao')
        }),
        ('Valores e Status', {
            'fields': ('valor_total', 'vencimento', 'status')
        }),
        ('Integração InfinitePay', {
            'fields': (
                'order_nsu', 'invoice_slug', 'checkout_url', 'transaction_nsu',
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
    
    def contrato_vinculado(self, obj):
        total = obj.itens_contrato.count()
        if total == 0:
            return '—'
        return f"{total} contrato(s)"
    contrato_vinculado.short_description = 'Contrato'

    def save_formset(self, request, form, formset, change):
        formset.save()

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


@admin.register(MessageQueue)
class MessageQueueAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'tipo', 'status', 'agendado_para', 'tentativas', 'enviado_em')
    list_filter = ('tipo', 'status')
    search_fields = ('invoice__id', 'telefone', 'mensagem')
    date_hierarchy = 'agendado_para'
