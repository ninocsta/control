from pathlib import Path

from django.utils import timezone

CSS = Path(__file__).resolve().parent / 'static' / 'painel' / 'app.css'


def nav(request):
    """Contadores do menu (só nas telas do painel)."""
    match = getattr(request, 'resolver_match', None)
    if not match or match.namespace != 'painel' or not request.user.is_authenticated:
        return {}
    from invoices.models import Invoice
    hoje = timezone.localdate()
    try:
        asset_v = int(CSS.stat().st_mtime)
    except OSError:
        asset_v = 0
    return {
        'asset_v': asset_v,
        'hoje': hoje,
        'nav_atrasadas': Invoice.objects.filter(status__in=['pendente', 'atrasado'], vencimento__lt=hoje).count(),
    }
