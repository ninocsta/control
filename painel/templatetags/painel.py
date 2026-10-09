from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def brl(valor):
    """1234.5 -> 'R$ 1.234,50'."""
    if valor in (None, ''):
        return '—'
    texto = f'{Decimal(valor):,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return f'R$ {texto}'


@register.filter
def quando(dias):
    """Dias relativos a hoje em texto curto."""
    if dias is None:
        return ''
    if dias == 0:
        return 'hoje'
    if dias == 1:
        return 'amanhã'
    if dias == -1:
        return 'ontem'
    return f'em {dias}d' if dias > 0 else f'há {-dias}d'
