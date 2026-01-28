from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Avg
from decimal import Decimal
from .models import PeriodoFinanceiro, ContratoSnapshot


@staff_member_required
def dashboard_financeiro(request):
    """
    Dashboard financeiro com visão consolidada dos períodos fechados.
    """
    # 1. Buscar todos os snapshots de períodos fechados
    snapshots = ContratoSnapshot.objects.filter(
        periodo__fechado=True
    ).select_related('contrato', 'periodo')
    
    # 2. Estatísticas gerais
    stats = {
        'receita_total': snapshots.aggregate(Sum('receita'))['receita__sum'] or Decimal('0.00'),
        'custo_total': snapshots.aggregate(Sum('custo_total'))['custo_total__sum'] or Decimal('0.00'),
        'margem_total': snapshots.aggregate(Sum('margem'))['margem__sum'] or Decimal('0.00'),
    }
    
    # Calcular margem percentual geral
    if stats['receita_total'] > 0:
        stats['margem_percentual'] = (stats['margem_total'] / stats['receita_total'] * 100)
    else:
        stats['margem_percentual'] = Decimal('0.00')
    
    # 3. Resumo por período
    periodos = PeriodoFinanceiro.objects.filter(fechado=True).order_by('-ano', '-mes')[:12]
    periodos_resumo = []
    
    for periodo in periodos:
        snaps = periodo.contrato_snapshots.all()
        receita = sum(s.receita for s in snaps)
        custo = sum(s.custo_total for s in snaps)
        margem = receita - custo
        margem_pct = (margem / receita * 100) if receita > 0 else Decimal('0.00')
        
        periodos_resumo.append({
            'mes': periodo.mes,
            'ano': periodo.ano,
            'receita': receita,
            'custo': custo,
            'margem_pct': margem_pct
        })
    
    # 4. Top contratos mais lucrativos
    from contratos.models import Contrato
    from django.db.models import Avg, Count
    
    contratos_com_snapshots = Contrato.objects.filter(
        snapshots__periodo__fechado=True
    ).annotate(
        margem_media=Avg('snapshots__margem'),
        margem_pct_media=Avg('snapshots__margem_percentual'),
        total_snapshots=Count('snapshots')
    ).order_by('-margem_media')[:10]
    
    top_contratos = []
    for contrato in contratos_com_snapshots:
        top_contratos.append({
            'nome': f"{contrato.nome} ({contrato.cliente.nome})",
            'margem_media': contrato.margem_media,
            'margem_pct': contrato.margem_pct_media
        })
    
    # 5. Custos por categoria
    custos_por_categoria = []
    
    if snapshots.exists():
        total_custo = stats['custo_total']
        
        categorias = [
            ('Domínios', snapshots.aggregate(Sum('custo_dominios'))['custo_dominios__sum'] or Decimal('0.00')),
            ('Hostings', snapshots.aggregate(Sum('custo_hostings'))['custo_hostings__sum'] or Decimal('0.00')),
            ('VPS', snapshots.aggregate(Sum('custo_vps'))['custo_vps__sum'] or Decimal('0.00')),
            ('Backups', snapshots.aggregate(Sum('custo_backups'))['custo_backups__sum'] or Decimal('0.00')),
            ('Emails', snapshots.aggregate(Sum('custo_emails'))['custo_emails__sum'] or Decimal('0.00')),
        ]
        
        for nome, valor in categorias:
            percentual = (valor / total_custo * 100) if total_custo > 0 else Decimal('0.00')
            custos_por_categoria.append({
                'nome': nome,
                'valor': valor,
                'percentual': percentual
            })
    
    context = {
        'stats': stats,
        'periodos_resumo': periodos_resumo,
        'top_contratos': top_contratos,
        'custos_por_categoria': custos_por_categoria,
    }
    
    return render(request, 'admin/financeiro/dashboard.html', context)
