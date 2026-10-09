import calendar

from django.contrib import admin


def somar_meses(data, meses):
    mes = data.month - 1 + meses
    ano = data.year + mes // 12
    mes = mes % 12 + 1
    return data.replace(year=ano, month=mes, day=min(data.day, calendar.monthrange(ano, mes)[1]))


@admin.action(description='Renovar: avançar vencimento pelo período (meses)')
def renovar(modeladmin, request, queryset):
    for cost in queryset:
        cost.vencimento = somar_meses(cost.vencimento, cost.periodo_meses)
        cost.save(update_fields=['vencimento'])
    modeladmin.message_user(request, f'{queryset.count()} vencimento(s) renovado(s).')
