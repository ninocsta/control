from django.contrib import admin
from .models import Cliente
from contratos.models import Contrato


class ContratoInline(admin.TabularInline):
    model = Contrato
    extra = 0
    fields = ('nome', 'valor_mensal', 'data_inicio', 'data_fim')
    show_change_link = True
    readonly_fields = ('nome', 'valor_mensal', 'data_inicio', 'data_fim')
    can_delete = False


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'email', 'tipo', 'ativo', 'data_criacao')
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
        ('Status', {
            'fields': ('ativo',)
        }),
    )
