from django.contrib import admin
from .models import Cliente
from contratos.models import Contrato


class ContratoInline(admin.TabularInline):
    model = Contrato
    extra = 0
    fields = ('nome', 'valor_mensal', 'data_inicio')
    show_change_link = True


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'email', 'tipo', 'vencimento_padrao', 'ativo', 'data_criacao')
    list_filter = ('tipo', 'ativo', 'data_criacao')
    search_fields = ('nome', 'email')
    inlines = [ContratoInline]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'email', 'telefone')
        }),
        ('Tipo', {
            'fields': ('tipo',)
        }),
        ('Cobrança', {
            'fields': ('vencimento_padrao',)
        }),
        ('Status', {
            'fields': ('ativo',)
        }),
    )
