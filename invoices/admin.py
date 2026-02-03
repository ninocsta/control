from django.contrib import admin
from django.forms import BaseInlineFormSet
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from .models import Invoice, InvoiceContrato


class InvoiceContratoInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        invoice = getattr(self, 'instance', None)
        if not invoice or not invoice.pk:
            return
        for form in self.forms:
            if form.instance.pk:
                continue
            if form.initial.get('valor'):
                continue
            form.initial['valor'] = invoice.valor_total

    def clean(self):
        super().clean()
        count = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                count += 1
                invoice = getattr(self, 'instance', None)
                if invoice and invoice.valor_total is not None:
                    form.cleaned_data['valor'] = invoice.valor_total
        if count == 0:
            raise ValidationError('Informe o contrato vinculado ao invoice.')


class InvoiceContratoInline(admin.TabularInline):
    model = InvoiceContrato
    formset = InvoiceContratoInlineFormSet
    extra = 0
    max_num = 1
    autocomplete_fields = ('contrato',)
    fields = ('contrato', 'valor', 'criado_em')
    readonly_fields = ('valor', 'criado_em')

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
    
    def contrato_vinculado(self, obj):
        item = obj.itens_contrato.select_related('contrato').first()
        if not item:
            return '—'
        return item.contrato.nome
    contrato_vinculado.short_description = 'Contrato'

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            instance.valor = form.instance.valor_total
            instance.save()
        formset.save_m2m()

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
