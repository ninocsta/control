from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from .services.dashboard_service import DashboardService


@staff_member_required
def dashboard_financeiro(request):
    """
    Dashboard Financeiro e Operacional.
    
    Princípios:
    - Snapshots são IMUTÁVEIS
    - Períodos fechados são fonte de verdade
    - Dashboard = leitura, nunca cálculo crítico
    """
    service = DashboardService()
    
    context = {
        # Cards principais (topo)
        'cards': service.get_cards_principais(),
        
        # Análise por contrato (últimos 3 meses)
        'analise_contratos': service.get_analise_contratos(limit=10),
        
        # Vencimentos próximos (30 dias)
        'vencimentos': service.get_vencimentos_proximos(dias=30),
        
        # Custos por categoria
        'custos_categorias': service.get_custos_por_categoria(),
        
        # Custos por cliente
        'custos_clientes': service.get_custos_por_cliente(limit=10),
        
        # Evolução mensal (gráfico)
        'evolucao_mensal': service.get_evolucao_mensal(meses=12),
    }
    
    return render(request, 'admin/financeiro/dashboard.html', context)
