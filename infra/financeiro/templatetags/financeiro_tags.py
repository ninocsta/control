from django import template

register = template.Library()


@register.filter(name='margem_format')
def margem_format(value, decimals=1):
    """
    Formata margem percentual.
    Retorna 'Interno' se valor for None (contratos internos).
    Caso contrário, formata como percentual.
    """
    if value is None:
        return '<span style="color: #9C27B0;">Interno</span>'
    
    try:
        formatted = f"{float(value):.{decimals}f}%"
        return formatted
    except (ValueError, TypeError):
        return 'N/A'


@register.filter(name='abs')
def abs_filter(value):
    """
    Retorna o valor absoluto de um número.
    """
    try:
        return abs(int(value))
    except (ValueError, TypeError):
        return value
