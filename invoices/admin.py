from django.contrib import admin, messages
from django.db import transaction
from django.forms import BaseInlineFormSet
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from .models import Invoice, InvoiceContrato, MessageQueue
from .services.invoice_service import recalcular_total, registrar_pagamento
from .services.message_queue_service import remover_mensagens_cobranca_pendentes


def _enviar_confirmacao_apos_commit(mensagem):
    if mensagem:
        from .tasks import task_enviar_confirmacao_imediata
        transaction.on_commit(lambda: task_enviar_confirmacao_imediata(mensagem.id), robust=True)


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
        'get_invoice_number', 'cliente', 'tipo', 'contrato_vinculado', 'valor_total_display',
        'vencimento', 'status_badge', 'pago_em', 'order_nsu', 'invoice_slug'
    )
    list_filter = (
        'status', 'tipo', 'ano_referencia', 'mes_referencia', 'cliente',
        'vencimento',
    )
    search_fields = (
        'cliente__nome', 'order_nsu', 'invoice_slug', 'transaction_nsu',
    )
    date_hierarchy = 'vencimento'
    readonly_fields = ('criado_em', 'valor_total')
    inlines = (InvoiceContratoInline,)
    actions = ('marcar_pago_manual', 'cancelar')

    fieldsets = (
        ('Cliente e Período', {
            'fields': ('cliente', 'tipo', 'mes_referencia', 'ano_referencia', 'descricao')
        }),
        ('Valores e Status', {
            'description': 'Valor = soma dos contratos abaixo. Marcar como pago aqui (Pix direto, '
                           'dinheiro) envia a confirmação ao cliente.',
            'fields': ('valor_total', 'vencimento', 'status', 'pago_em')
        }),
        ('Integração InfinitePay', {
            'fields': (
                'order_nsu', 'invoice_slug', 'checkout_url', 'transaction_nsu',
                'capture_method', 'receipt_url'
            ),
            'classes': ('collapse',)
        }),
        ('Controle', {
            'fields': ('criado_em',),
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

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        invoice = form.instance
        if recalcular_total(invoice) and invoice.em_aberto:
            self.message_user(request, 'Valor mudou: link de pagamento refeito.', messages.INFO)
        status_antes = form.initial.get('status')
        if invoice.status == 'pago' and status_antes != 'pago':
            _enviar_confirmacao_apos_commit(registrar_pagamento(invoice, capture_method=invoice.capture_method or 'manual'))
        elif invoice.status == 'cancelado' and status_antes != 'cancelado':
            remover_mensagens_cobranca_pendentes(invoice)

    @admin.action(description='Marcar como pago (Pix direto/dinheiro) e avisar o cliente')
    def marcar_pago_manual(self, request, queryset):
        total = 0
        for invoice in queryset.exclude(status__in=['pago', 'cancelado']):
            _enviar_confirmacao_apos_commit(registrar_pagamento(invoice, capture_method='manual'))
            total += 1
        self.message_user(request, f'{total} fatura(s) marcada(s) como paga(s).')

    @admin.action(description='Cancelar (o link /p/ passa a mostrar "cancelada")')
    def cancelar(self, request, queryset):
        total = 0
        for invoice in queryset.exclude(status__in=['pago', 'cancelado']):
            invoice.status = 'cancelado'
            invoice.save(update_fields=['status'])
            remover_mensagens_cobranca_pendentes(invoice)
            total += 1
        self.message_user(request, f'{total} fatura(s) cancelada(s).')

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
