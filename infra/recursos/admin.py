from django.contrib import admin

from infra.core.admin import renovar
from .models import CustoRecurso, Recurso, RecursoContrato


class RecursoContratoInline(admin.TabularInline):
    model = RecursoContrato
    extra = 0
    autocomplete_fields = ('contrato',)


class CustoRecursoInline(admin.TabularInline):
    model = CustoRecurso
    extra = 0
    fields = ('valor_total', 'periodo_meses', 'data_inicio', 'data_fim', 'vencimento', 'pago_pelo_cliente', 'ativo')


@admin.register(Recurso)
class RecursoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'fornecedor', 'pai', 'ativo')
    list_filter = ('tipo', 'ativo', 'fornecedor')
    search_fields = ('nome', 'fornecedor', 'detalhe')
    inlines = (RecursoContratoInline, CustoRecursoInline)


@admin.register(CustoRecurso)
class CustoRecursoAdmin(admin.ModelAdmin):
    list_display = ('recurso', 'valor_total', 'periodo_meses', 'vencimento', 'pago_pelo_cliente', 'ativo')
    list_filter = ('ativo', 'pago_pelo_cliente', 'recurso__tipo')
    search_fields = ('recurso__nome',)
    actions = [renovar]
