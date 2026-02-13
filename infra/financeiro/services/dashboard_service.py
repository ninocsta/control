"""
Service para Dashboard Financeiro e Operacional.

Princípios:
- Snapshots são IMUTÁVEIS
- Períodos fechados são fonte de verdade
- Dashboard = leitura, nunca cálculo crítico
- Performance > beleza
"""
from decimal import Decimal
from datetime import date, timedelta
from django.db.models import Sum, Avg, Count, Q, F
from django.utils import timezone

from infra.financeiro.models import PeriodoFinanceiro, ContratoSnapshot, DespesaAdicional
from contratos.models import Contrato
from invoices.models import Invoice, MessageQueue
from infra.dominios.models import DomainCost
from infra.vps.models import VPSCost
from infra.hosting.models import HostingCost
from infra.emails.models import DomainEmailCost
from infra.backups.models import VPSBackupCost


class DashboardService:
    """
    Service centralizado para todas as queries do dashboard.
    Garante performance e consistência.
    """
    
    def __init__(self):
        self.hoje = date.today()
        self.primeiro_dia_mes_atual = date(self.hoje.year, self.hoje.month, 1)
    
    # ========================================
    # 1️⃣ CARDS PRINCIPAIS (TOPO)
    # ========================================
    
    def get_cards_principais(self):
        """
        Retorna dados dos cards principais do dashboard.
        
        Fonte: Último período fechado + Previsão mês atual
        """
        # Último período fechado
        ultimo_periodo = PeriodoFinanceiro.objects.filter(
            fechado=True
        ).order_by('-ano', '-mes').first()
        
        # Previsão do mês atual (NÃO usar snapshots)
        previsao = self._calcular_previsao_mes_atual()

        # Receita emitida e paga do mês atual
        mes_atual = self.hoje.month
        ano_atual = self.hoje.year
        invoices_mes_atual = Invoice.objects.filter(
            mes_referencia=mes_atual,
            ano_referencia=ano_atual
        ).exclude(status='cancelado')

        receita_emitida_mes_atual = invoices_mes_atual.aggregate(
            total=Sum('valor_total')
        )['total'] or Decimal('0.00')
        receita_paga_mes_atual = invoices_mes_atual.filter(status='pago').aggregate(
            total=Sum('valor_total')
        )['total'] or Decimal('0.00')

        if not ultimo_periodo:
            return self._cards_vazios(
                previsao=previsao,
                receita_emitida_mes_atual=receita_emitida_mes_atual,
                receita_paga_mes_atual=receita_paga_mes_atual,
            )
        
        # Dados do último período fechado
        snapshots = ContratoSnapshot.objects.filter(
            periodo=ultimo_periodo
        ).select_related('contrato', 'periodo')
        
        receita_total = snapshots.aggregate(Sum('receita'))['receita__sum'] or Decimal('0.00')
        despesa_total = snapshots.aggregate(Sum('custo_total'))['custo_total__sum'] or Decimal('0.00')
        lucro_total = receita_total - despesa_total
        
        # Calcular margem % apenas se houver receita
        # Contratos internos (receita zero) não têm margem percentual
        if receita_total > 0:
            margem_pct = (lucro_total / receita_total * 100)
        else:
            margem_pct = None
        
        return {
            'ultimo_periodo': {
                'mes': ultimo_periodo.mes,
                'ano': ultimo_periodo.ano,
                'nome': f"{ultimo_periodo.mes:02d}/{ultimo_periodo.ano}"
            },
            'receita_total': receita_total,
            'despesa_total': despesa_total,
            'lucro_total': lucro_total,
            'margem_pct': margem_pct,
            'previsao_receita': previsao['receita_invoices'],
            'previsao_receita_contratos': previsao['receita_contratos'],
            'previsao_despesa': previsao['despesa'],
            'previsao_lucro': previsao['lucro_invoices'],
            'previsao_margem_pct': previsao['margem_pct_invoices'],
            'receita_emitida_mes_atual': receita_emitida_mes_atual,
            'receita_paga_mes_atual': receita_paga_mes_atual,
        }
    
    def _cards_vazios(self, previsao=None, receita_emitida_mes_atual=None, receita_paga_mes_atual=None):
        """Retorna estrutura vazia quando não há dados."""
        previsao = previsao or {
            'receita_invoices': Decimal('0.00'),
            'receita_contratos': Decimal('0.00'),
            'despesa': Decimal('0.00'),
            'lucro_invoices': Decimal('0.00'),
            'margem_pct_invoices': Decimal('0.00'),
            'lucro_contratos': Decimal('0.00'),
            'margem_pct_contratos': Decimal('0.00'),
        }
        receita_emitida_mes_atual = receita_emitida_mes_atual or Decimal('0.00')
        receita_paga_mes_atual = receita_paga_mes_atual or Decimal('0.00')
        return {
            'ultimo_periodo': None,
            'receita_total': Decimal('0.00'),
            'despesa_total': Decimal('0.00'),
            'lucro_total': Decimal('0.00'),
            'margem_pct': Decimal('0.00'),
            'previsao_receita': previsao['receita_invoices'],
            'previsao_receita_contratos': previsao['receita_contratos'],
            'previsao_despesa': previsao['despesa'],
            'previsao_lucro': previsao['lucro_invoices'],
            'previsao_margem_pct': previsao['margem_pct_invoices'],
            'receita_emitida_mes_atual': receita_emitida_mes_atual,
            'receita_paga_mes_atual': receita_paga_mes_atual,
        }
    
    def _calcular_previsao_mes_atual(self):
        """
        Calcula previsão do mês atual usando invoices e contratos (comparativo).
        NÃO cria snapshots, apenas simulação.
        """
        # Invoices do mês atual (receita planejada)
        receita_invoices = (
            Invoice.objects.filter(
                mes_referencia=self.primeiro_dia_mes_atual.month,
                ano_referencia=self.primeiro_dia_mes_atual.year
            ).exclude(
                status='cancelado'
            ).aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
        )

        # Contratos ativos no mês atual (previsão alternativa)
        contratos_ativos = Contrato.objects.filter(
            data_inicio__lte=self.primeiro_dia_mes_atual
        ).filter(
            Q(data_fim__isnull=True) | Q(data_fim__gte=self.primeiro_dia_mes_atual)
        )
        receita_contratos = sum(c.valor_mensal for c in contratos_ativos)
        
        # Custos ativos (soma de todas as categorias)
        despesa = Decimal('0.00')
        despesa += self._somar_custos_ativos(DomainCost)
        despesa += self._somar_custos_ativos(VPSCost)
        despesa += self._somar_custos_ativos(HostingCost)
        despesa += self._somar_custos_ativos(DomainEmailCost)
        despesa += self._somar_custos_ativos(VPSBackupCost)
        despesa += (
            DespesaAdicional.objects.filter(
                mes_referencia=self.primeiro_dia_mes_atual.month,
                ano_referencia=self.primeiro_dia_mes_atual.year,
            ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        )

        lucro_invoices = receita_invoices - despesa
        margem_pct_invoices = (lucro_invoices / receita_invoices * 100) if receita_invoices > 0 else Decimal('0.00')

        lucro_contratos = receita_contratos - despesa
        margem_pct_contratos = (lucro_contratos / receita_contratos * 100) if receita_contratos > 0 else Decimal('0.00')
        
        return {
            'receita_invoices': receita_invoices,
            'receita_contratos': receita_contratos,
            'despesa': despesa,
            'lucro_invoices': lucro_invoices,
            'margem_pct_invoices': margem_pct_invoices,
            'lucro_contratos': lucro_contratos,
            'margem_pct_contratos': margem_pct_contratos,
        }
    
    def _somar_custos_ativos(self, model_class):
        """Soma custo mensal de um tipo de custo ativo."""
        custos = model_class.objects.filter(
            data_inicio__lte=self.primeiro_dia_mes_atual,
            ativo=True
        ).filter(
            Q(data_fim__isnull=True) | Q(data_fim__gte=self.primeiro_dia_mes_atual)
        )
        
        total = Decimal('0.00')
        for custo in custos:
            total += custo.custo_mensal
        
        return total
    
    # ========================================
    # 2️⃣ ANÁLISE POR CONTRATO (ÚLTIMOS 3 MESES)
    # ========================================
    
    def get_analise_contratos(self, limit=10):
        """
        Retorna análise detalhada dos últimos 3 períodos por contrato.
        
        Para cada contrato:
        - Receita (por mês)
        - Custo total (por mês)
        - Lucro (por mês)
        - Margem (%)
        - Tendência
        """
        # Últimos 3 períodos fechados
        periodos = PeriodoFinanceiro.objects.filter(
            fechado=True
        ).order_by('-ano', '-mes')[:3]
        
        if not periodos.exists():
            return []
        
        periodos_list = list(periodos)
        periodos_list.reverse()  # Ordem cronológica
        
        # Buscar contratos com snapshots nesses períodos
        contratos = Contrato.objects.filter(
            snapshots__periodo__in=periodos
        ).distinct().select_related('cliente')
        
        resultado = []
        
        for contrato in contratos:
            snapshots_contrato = ContratoSnapshot.objects.filter(
                contrato=contrato,
                periodo__in=periodos
            ).select_related('periodo').order_by('periodo__ano', 'periodo__mes')
            
            dados_meses = []
            for snapshot in snapshots_contrato:
                # Para contratos internos, margem_percentual pode ser NULL
                margem_pct = snapshot.margem_percentual if snapshot.margem_percentual is not None else None
                dados_meses.append({
                    'mes': f"{snapshot.periodo.mes:02d}/{snapshot.periodo.ano}",
                    'receita': snapshot.receita,
                    'custo': snapshot.custo_total,
                    'lucro': snapshot.margem,
                    'margem_pct': margem_pct,
                    'is_interno': snapshot.contrato.cliente.tipo == 'interno'
                })
            
            # Calcular tendência (último mês vs primeiro mês)
            if len(dados_meses) >= 2:
                lucro_inicial = dados_meses[0]['lucro']
                lucro_final = dados_meses[-1]['lucro']
                
                if lucro_final > lucro_inicial:
                    tendencia = '↑'
                    tendencia_cor = 'green'
                elif lucro_final < lucro_inicial:
                    tendencia = '↓'
                    tendencia_cor = 'red'
                else:
                    tendencia = '='
                    tendencia_cor = 'gray'
            else:
                tendencia = '='
                tendencia_cor = 'gray'
            
            # Médias
            margem_media = sum(m['lucro'] for m in dados_meses) / len(dados_meses) if dados_meses else Decimal('0.00')
            
            resultado.append({
                'contrato': contrato,
                'cliente': contrato.cliente.nome,
                'meses': dados_meses,
                'tendencia': tendencia,
                'tendencia_cor': tendencia_cor,
                'margem_media': margem_media
            })
        
        # Ordenar por margem média (decrescente)
        resultado.sort(key=lambda x: x['margem_media'], reverse=True)
        
        return resultado[:limit]
    
    # ========================================
    # 3️⃣ VENCIMENTOS (PRÓXIMOS 30 DIAS)
    # ========================================
    
    def get_vencimentos_proximos(self, dias=30):
        """
        Retorna todos os custos que vencem nos próximos X dias.
        
        Exibe item por item (não agrupa).
        Ordenado por data de vencimento.
        """
        data_limite = self.hoje + timedelta(days=dias)
        
        vencimentos = []
        
        # Domínios
        dominios = DomainCost.objects.filter(
            vencimento__gte=self.hoje,
            vencimento__lte=data_limite,
            ativo=True
        ).select_related('domain').order_by('vencimento')
        
        for custo in dominios:
            dias_restantes = (custo.vencimento - self.hoje).days
            vencimentos.append({
                'tipo': 'Domínio',
                'nome': custo.domain.nome,
                'fornecedor': custo.domain.fornecedor,
                'valor': custo.valor_total,
                'vencimento': custo.vencimento,
                'dias_restantes': dias_restantes,
                'urgencia': self._calcular_urgencia(dias_restantes)
            })
        
        # VPS
        vps_costs = VPSCost.objects.filter(
            vencimento__gte=self.hoje,
            vencimento__lte=data_limite,
            ativo=True
        ).select_related('vps').order_by('vencimento')
        
        for custo in vps_costs:
            dias_restantes = (custo.vencimento - self.hoje).days
            vencimentos.append({
                'tipo': 'VPS',
                'nome': custo.vps.nome,
                'fornecedor': custo.vps.fornecedor,
                'valor': custo.valor_total,
                'vencimento': custo.vencimento,
                'dias_restantes': dias_restantes,
                'urgencia': self._calcular_urgencia(dias_restantes)
            })
        
        # Hostings
        hostings = HostingCost.objects.filter(
            vencimento__gte=self.hoje,
            vencimento__lte=data_limite,
            ativo=True
        ).select_related('hosting').order_by('vencimento')
        
        for custo in hostings:
            dias_restantes = (custo.vencimento - self.hoje).days
            vencimentos.append({
                'tipo': 'Hosting',
                'nome': custo.hosting.nome,
                'fornecedor': custo.hosting.fornecedor,
                'valor': custo.valor_total,
                'vencimento': custo.vencimento,
                'dias_restantes': dias_restantes,
                'urgencia': self._calcular_urgencia(dias_restantes)
            })
        
        # Emails
        emails = DomainEmailCost.objects.filter(
            vencimento__gte=self.hoje,
            vencimento__lte=data_limite,
            ativo=True
        ).select_related('email__dominio').order_by('vencimento')
        
        for custo in emails:
            dias_restantes = (custo.vencimento - self.hoje).days
            vencimentos.append({
                'tipo': 'Email',
                'nome': f"Email {custo.email.dominio.nome}",
                'fornecedor': custo.email.fornecedor,
                'valor': custo.valor_total,
                'vencimento': custo.vencimento,
                'dias_restantes': dias_restantes,
                'urgencia': self._calcular_urgencia(dias_restantes)
            })
        
        # Backups
        backups = VPSBackupCost.objects.filter(
            vencimento__gte=self.hoje,
            vencimento__lte=data_limite,
            ativo=True
        ).select_related('backup__vps').order_by('vencimento')
        
        for custo in backups:
            dias_restantes = (custo.vencimento - self.hoje).days
            vencimentos.append({
                'tipo': 'Backup',
                'nome': f"{custo.backup.nome} ({custo.backup.vps.nome})",
                'fornecedor': custo.backup.fornecedor or custo.backup.vps.fornecedor,
                'valor': custo.valor_total,
                'vencimento': custo.vencimento,
                'dias_restantes': dias_restantes,
                'urgencia': self._calcular_urgencia(dias_restantes)
            })
        
        # Ordenar por vencimento (mais próximo primeiro)
        vencimentos.sort(key=lambda x: x['vencimento'])
        
        return vencimentos
    
    def _calcular_urgencia(self, dias_restantes):
        """Define nível de urgência baseado em dias restantes."""
        if dias_restantes <= 0:
            return {'nivel': 'vencido', 'cor': '#8b0000', 'texto': 'VENCIDO'}
        elif dias_restantes <= 7:
            return {'nivel': 'alta', 'cor': '#dc3545', 'texto': 'URGENTE'}
        elif dias_restantes <= 15:
            return {'nivel': 'media', 'cor': '#ffc107', 'texto': 'Atenção'}
        else:
            return {'nivel': 'baixa', 'cor': '#28a745', 'texto': 'Normal'}
    
    def get_vencimentos_incluindo_vencidos(self, dias_futuro=30, dias_passado=30):
        """
        Retorna vencimentos incluindo itens já vencidos.
        
        Args:
            dias_futuro: Quantos dias no futuro buscar
            dias_passado: Quantos dias no passado buscar (vencidos)
        """
        data_inicio = self.hoje - timedelta(days=dias_passado)
        data_limite = self.hoje + timedelta(days=dias_futuro)
        
        vencimentos = []
        
        # Domínios
        dominios = DomainCost.objects.filter(
            vencimento__gte=data_inicio,
            vencimento__lte=data_limite,
            ativo=True
        ).select_related('domain').order_by('vencimento')
        
        for custo in dominios:
            dias_restantes = (custo.vencimento - self.hoje).days
            vencimentos.append({
                'tipo': 'Domínio',
                'nome': custo.domain.nome,
                'fornecedor': custo.domain.fornecedor,
                'valor': custo.valor_total,
                'vencimento': custo.vencimento,
                'dias_restantes': dias_restantes,
                'urgencia': self._calcular_urgencia(dias_restantes),
                'vencido': dias_restantes < 0
            })
        
        # VPS
        vps_costs = VPSCost.objects.filter(
            vencimento__gte=data_inicio,
            vencimento__lte=data_limite,
            ativo=True
        ).select_related('vps').order_by('vencimento')
        
        for custo in vps_costs:
            dias_restantes = (custo.vencimento - self.hoje).days
            vencimentos.append({
                'tipo': 'VPS',
                'nome': custo.vps.nome,
                'fornecedor': custo.vps.fornecedor,
                'valor': custo.valor_total,
                'vencimento': custo.vencimento,
                'dias_restantes': dias_restantes,
                'urgencia': self._calcular_urgencia(dias_restantes),
                'vencido': dias_restantes < 0
            })
        
        # Hostings
        hostings = HostingCost.objects.filter(
            vencimento__gte=data_inicio,
            vencimento__lte=data_limite,
            ativo=True
        ).select_related('hosting').order_by('vencimento')
        
        for custo in hostings:
            dias_restantes = (custo.vencimento - self.hoje).days
            vencimentos.append({
                'tipo': 'Hosting',
                'nome': custo.hosting.nome,
                'fornecedor': custo.hosting.fornecedor,
                'valor': custo.valor_total,
                'vencimento': custo.vencimento,
                'dias_restantes': dias_restantes,
                'urgencia': self._calcular_urgencia(dias_restantes),
                'vencido': dias_restantes < 0
            })
        
        # Emails
        emails = DomainEmailCost.objects.filter(
            vencimento__gte=data_inicio,
            vencimento__lte=data_limite,
            ativo=True
        ).select_related('email__dominio').order_by('vencimento')
        
        for custo in emails:
            dias_restantes = (custo.vencimento - self.hoje).days
            vencimentos.append({
                'tipo': 'Email',
                'nome': f"Email {custo.email.dominio.nome}",
                'fornecedor': custo.email.fornecedor,
                'valor': custo.valor_total,
                'vencimento': custo.vencimento,
                'dias_restantes': dias_restantes,
                'urgencia': self._calcular_urgencia(dias_restantes),
                'vencido': dias_restantes < 0
            })
        
        # Backups
        backups = VPSBackupCost.objects.filter(
            vencimento__gte=data_inicio,
            vencimento__lte=data_limite,
            ativo=True
        ).select_related('backup__vps').order_by('vencimento')
        
        for custo in backups:
            dias_restantes = (custo.vencimento - self.hoje).days
            vencimentos.append({
                'tipo': 'Backup',
                'nome': f"{custo.backup.nome} ({custo.backup.vps.nome})",
                'fornecedor': custo.backup.fornecedor or custo.backup.vps.fornecedor,
                'valor': custo.valor_total,
                'vencimento': custo.vencimento,
                'dias_restantes': dias_restantes,
                'urgencia': self._calcular_urgencia(dias_restantes),
                'vencido': dias_restantes < 0
            })
        
        # Ordenar: vencidos primeiro (mais antigos), depois próximos (mais próximos)
        vencimentos.sort(key=lambda x: (not x['vencido'], x['vencimento']))
        
        return vencimentos
    
    def get_status_invoices(self):
        """
        Retorna status dos invoices do mês atual e meses anteriores em atraso.
        """
        mes_atual = self.hoje.month
        ano_atual = self.hoje.year
        
        # Invoices do mês atual
        invoices_mes_atual = Invoice.objects.filter(
            mes_referencia=mes_atual,
            ano_referencia=ano_atual
        ).select_related('cliente').order_by('status', 'vencimento')
        
        # Invoices em atraso (meses anteriores não pagos)
        invoices_atrasados = Invoice.objects.filter(
            Q(ano_referencia__lt=ano_atual) | 
            Q(ano_referencia=ano_atual, mes_referencia__lt=mes_atual),
            status__in=['pendente', 'atrasado']
        ).select_related('cliente').order_by('ano_referencia', 'mes_referencia')
        
        # Calcular totais mês atual
        total_mes_atual = invoices_mes_atual.aggregate(Sum('valor_total'))['valor_total__sum'] or Decimal('0.00')
        pagos_mes_atual = invoices_mes_atual.filter(status='pago').aggregate(Sum('valor_total'))['valor_total__sum'] or Decimal('0.00')
        pendentes_mes_atual = invoices_mes_atual.filter(status='pendente').aggregate(Sum('valor_total'))['valor_total__sum'] or Decimal('0.00')
        atrasados_mes_atual = invoices_mes_atual.filter(status='atrasado').aggregate(Sum('valor_total'))['valor_total__sum'] or Decimal('0.00')
        
        # Calcular totais atrasados
        total_atrasados = invoices_atrasados.aggregate(Sum('valor_total'))['valor_total__sum'] or Decimal('0.00')
        
        return {
            'mes_atual': {
                'mes': mes_atual,
                'ano': ano_atual,
                'total': total_mes_atual,
                'pago': pagos_mes_atual,
                'pendente': pendentes_mes_atual,
                'atrasado': atrasados_mes_atual,
                'qtd_total': invoices_mes_atual.count(),
                'qtd_pagos': invoices_mes_atual.filter(status='pago').count(),
                'qtd_pendentes': invoices_mes_atual.filter(status='pendente').count(),
                'qtd_atrasados': invoices_mes_atual.filter(status='atrasado').count(),
                'invoices': [{
                    'id': inv.id,
                    'cliente': inv.cliente.nome,
                    'valor': inv.valor_total,
                    'status': inv.status,
                    'vencimento': inv.vencimento,
                    'dias_vencimento': (inv.vencimento - self.hoje).days if inv.vencimento else None
                } for inv in invoices_mes_atual]
            },
            'atrasados': {
                'total': total_atrasados,
                'qtd': invoices_atrasados.count(),
                'invoices': [{
                    'id': inv.id,
                    'cliente': inv.cliente.nome,
                    'valor': inv.valor_total,
                    'mes_ref': f"{inv.mes_referencia:02d}/{inv.ano_referencia}",
                    'status': inv.status,
                    'vencimento': inv.vencimento,
                    'dias_atraso': (self.hoje - inv.vencimento).days if inv.vencimento else 0
                } for inv in invoices_atrasados]
            }
        }
    
    # ========================================
    # 4️⃣ CUSTOS POR CATEGORIA
    # ========================================
    
    def get_custos_por_categoria(self):
        """
        Retorna custos agrupados por categoria (último período fechado).
        """
        ultimo_periodo = PeriodoFinanceiro.objects.filter(
            fechado=True
        ).order_by('-ano', '-mes').first()
        
        if not ultimo_periodo:
            return []
        
        snapshots = ContratoSnapshot.objects.filter(periodo=ultimo_periodo)
        
        total_custo = snapshots.aggregate(Sum('custo_total'))['custo_total__sum'] or Decimal('0.00')
        
        if total_custo == 0:
            return []
        
        categorias = [
            {
                'nome': 'Domínios',
                'valor': snapshots.aggregate(Sum('custo_dominios'))['custo_dominios__sum'] or Decimal('0.00'),
                'cor': '#3498db'
            },
            {
                'nome': 'Hostings',
                'valor': snapshots.aggregate(Sum('custo_hostings'))['custo_hostings__sum'] or Decimal('0.00'),
                'cor': '#9b59b6'
            },
            {
                'nome': 'VPS',
                'valor': snapshots.aggregate(Sum('custo_vps'))['custo_vps__sum'] or Decimal('0.00'),
                'cor': '#e74c3c'
            },
            {
                'nome': 'Backups',
                'valor': snapshots.aggregate(Sum('custo_backups'))['custo_backups__sum'] or Decimal('0.00'),
                'cor': '#f39c12'
            },
            {
                'nome': 'Emails',
                'valor': snapshots.aggregate(Sum('custo_emails'))['custo_emails__sum'] or Decimal('0.00'),
                'cor': '#1abc9c'
            },
            {
                'nome': 'Despesas Adicionais',
                'valor': snapshots.aggregate(Sum('custo_despesas_adicionais'))['custo_despesas_adicionais__sum'] or Decimal('0.00'),
                'cor': '#6c757d'
            },
        ]
        
        for categoria in categorias:
            categoria['percentual'] = (categoria['valor'] / total_custo * 100) if total_custo > 0 else Decimal('0.00')
        
        # Ordenar por valor (decrescente)
        categorias.sort(key=lambda x: x['valor'], reverse=True)
        
        return categorias

    def get_alertas_anomalia(self):
        """
        Retorna alertas para possiveis anomalias operacionais.
        """
        mes_atual = self.hoje.month
        ano_atual = self.hoje.year

        alertas = []

        invoices_sem_checkout = Invoice.objects.filter(
            mes_referencia=mes_atual,
            ano_referencia=ano_atual,
            status__in=['pendente', 'atrasado']
        ).filter(
            Q(checkout_url='') | Q(checkout_url__isnull=True)
        ).count()
        if invoices_sem_checkout:
            alertas.append({
                'titulo': 'Invoices sem checkout',
                'descricao': f'{invoices_sem_checkout} invoice(s) pendente/atrasado sem link de checkout.',
                'nivel': 'alto',
                'cor': '#dc3545',
            })

        invoices_sem_vinculo = Invoice.objects.filter(
            mes_referencia=mes_atual,
            ano_referencia=ano_atual,
            itens_contrato__isnull=True
        ).count()
        if invoices_sem_vinculo:
            alertas.append({
                'titulo': 'Invoices sem vínculo',
                'descricao': f'{invoices_sem_vinculo} invoice(s) do mês sem vínculo de contrato.',
                'nivel': 'medio',
                'cor': '#ffc107',
            })

        invoices_sem_telefone = Invoice.objects.filter(
            mes_referencia=mes_atual,
            ano_referencia=ano_atual,
            status__in=['pendente', 'atrasado']
        ).filter(
            Q(cliente__telefone__isnull=True) | Q(cliente__telefone='')
        ).count()
        if invoices_sem_telefone:
            alertas.append({
                'titulo': 'Clientes sem telefone',
                'descricao': f'{invoices_sem_telefone} invoice(s) sem telefone para envio.',
                'nivel': 'medio',
                'cor': '#ffc107',
            })

        mensagens_pendentes = MessageQueue.objects.filter(
            status='pendente',
            agendado_para__lt=timezone.now() - timedelta(hours=12)
        ).count()
        if mensagens_pendentes:
            alertas.append({
                'titulo': 'Fila de mensagens atrasada',
                'descricao': f'{mensagens_pendentes} mensagem(ns) pendente(s) ha mais de 12h.',
                'nivel': 'alto',
                'cor': '#dc3545',
            })

        return alertas

    def get_receita_mes_atual_chart_data(self):
        """
        Dados para grafico de receita do mes atual.
        """
        previsao = self._calcular_previsao_mes_atual()
        mes_atual = self.hoje.month
        ano_atual = self.hoje.year
        invoices_mes_atual = Invoice.objects.filter(
            mes_referencia=mes_atual,
            ano_referencia=ano_atual
        ).exclude(status='cancelado')

        receita_emitida = invoices_mes_atual.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
        receita_paga = invoices_mes_atual.filter(status='pago').aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')

        return {
            'labels': ['Prev. Contratos', 'Emitida (Invoices)', 'Paga'],
            'values': [
                float(previsao['receita_contratos']),
                float(receita_emitida),
                float(receita_paga),
            ],
        }

    def get_custos_categoria_chart_data(self):
        """
        Dados para grafico de custos por categoria.
        """
        categorias = self.get_custos_por_categoria()
        return {
            'labels': [c['nome'] for c in categorias],
            'values': [float(c['valor']) for c in categorias],
            'colors': [c['cor'] for c in categorias],
        }
    
    # ========================================
    # 5️⃣ CUSTOS POR CLIENTE
    # ========================================
    
    def get_custos_por_cliente(self, limit=10):
        """
        Retorna custos agrupados por cliente (último período fechado).
        """
        ultimo_periodo = PeriodoFinanceiro.objects.filter(
            fechado=True
        ).order_by('-ano', '-mes').first()
        
        if not ultimo_periodo:
            return []
        
        from clientes.models import Cliente
        from django.db.models import Sum, Count
        
        # Agrupar snapshots por cliente
        clientes_data = ContratoSnapshot.objects.filter(
            periodo=ultimo_periodo
        ).values(
            'contrato__cliente__id',
            'contrato__cliente__nome'
        ).annotate(
            receita_total=Sum('receita'),
            custo_total=Sum('custo_total'),
            margem_total=Sum('margem'),
            num_contratos=Count('contrato', distinct=True)
        ).order_by('-margem_total')
        
        resultado = []
        for data in clientes_data[:limit]:
            margem_pct = Decimal('0.00')
            if data['receita_total'] > 0:
                margem_pct = (data['margem_total'] / data['receita_total'] * 100)
            
            # Definir cor baseado na margem
            if margem_pct >= 50:
                cor_margem = '#28a745'  # Verde
            elif margem_pct >= 30:
                cor_margem = '#ffc107'  # Amarelo
            else:
                cor_margem = '#dc3545'  # Vermelho
            
            resultado.append({
                'nome': data['contrato__cliente__nome'],
                'receita': data['receita_total'],
                'custo': data['custo_total'],
                'margem': data['margem_total'],
                'margem_pct': margem_pct,
                'num_contratos': data['num_contratos'],
                'cor_margem': cor_margem
            })
        
        return resultado
    
    # ========================================
    # 6️⃣ EVOLUÇÃO MENSAL (ÚLTIMOS 12 MESES)
    # ========================================
    
    def get_evolucao_mensal(self, meses=12):
        """
        Retorna evolução de receita, custo e margem dos últimos X meses.
        Útil para gráficos.
        """
        periodos = PeriodoFinanceiro.objects.filter(
            fechado=True
        ).order_by('-ano', '-mes')[:meses]
        
        resultado = []
        
        for periodo in reversed(periodos):
            snapshots = ContratoSnapshot.objects.filter(periodo=periodo)
            
            receita = snapshots.aggregate(Sum('receita'))['receita__sum'] or Decimal('0.00')
            custo = snapshots.aggregate(Sum('custo_total'))['custo_total__sum'] or Decimal('0.00')
            margem = receita - custo
            margem_pct = (margem / receita * 100) if receita > 0 else Decimal('0.00')
            
            resultado.append({
                'mes': f"{periodo.mes:02d}/{periodo.ano}",
                'mes_num': periodo.mes,
                'ano': periodo.ano,
                'receita': receita,
                'custo': custo,
                'margem': margem,
                'margem_pct': margem_pct
            })
        
        return resultado

    def get_evolucao_chart_data(self, meses=12):
        """
        Dados prontos para gráfico de evolução mensal (Chart.js).
        """
        dados = self.get_evolucao_mensal(meses=meses)
        return {
            'labels': [d['mes'] for d in dados],
            'receitas': [float(d['receita']) for d in dados],
            'custos': [float(d['custo']) for d in dados],
            'margens': [float(d['margem']) for d in dados],
        }
