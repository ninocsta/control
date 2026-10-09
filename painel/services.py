"""Leituras do painel: resumo do mês, agenda de datas e saúde do sistema."""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from contratos.models import Contrato, ContratoReajuste
from infra.financeiro.models import ContratoSnapshot, DespesaAdicional
from infra.financeiro.services.rateio import primeiro_e_proximo_mes
from infra.recursos.models import CustoRecurso
from infra.recursos.services import custos_monitorados
from invoices.models import Invoice, MessageQueue

from .templatetags.painel import brl

ZERO = Decimal('0.00')
MESES = ['', 'jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']


def mes_anterior(ano, mes):
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


def mes_seguinte(ano, mes):
    return (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def contratos_vigentes(primeiro_dia):
    """Mesmo critério da geração de faturas: começou até o dia 1 e não terminou antes."""
    return Contrato.objects.filter(data_inicio__lte=primeiro_dia, cliente__ativo=True).filter(
        Q(data_fim__isnull=True) | Q(data_fim__gte=primeiro_dia)
    ).select_related('cliente')


def _soma(qs):
    return qs.aggregate(t=Sum('valor_total'))['t'] or ZERO


def custo_previsto(ano, mes):
    """Custo mensal dos recursos que você paga + despesas adicionais do mês."""
    primeiro, proximo = primeiro_e_proximo_mes(mes, ano)
    custos = CustoRecurso.objects.filter(
        ativo=True, pago_pelo_cliente=False, data_inicio__lt=proximo,
    ).filter(Q(data_fim__isnull=True) | Q(data_fim__gte=primeiro))
    total = sum((c.custo_mensal for c in custos), ZERO)
    despesas = DespesaAdicional.objects.filter(mes_referencia=mes, ano_referencia=ano)
    return total + (despesas.aggregate(t=Sum('valor'))['t'] or ZERO)


def resumo_mes(ano, mes):
    hoje = timezone.localdate()
    primeiro = date(ano, mes, 1)
    faturas = Invoice.objects.filter(ano_referencia=ano, mes_referencia=mes).exclude(status='cancelado')
    previsto = sum((c.valor_em(primeiro) for c in contratos_vigentes(primeiro)), ZERO)
    faturado = _soma(faturas)
    recebido = _soma(faturas.filter(status='pago'))
    vencido = faturas.filter(status__in=['pendente', 'atrasado'], vencimento__lt=hoje)
    custo = custo_previsto(ano, mes)
    return {
        'ano': ano, 'mes': mes, 'rotulo': f'{MESES[mes]}/{ano}',
        'previsto': previsto,
        'faturado': faturado,
        'recebido': recebido,
        'a_receber': faturado - recebido,
        'vencido': _soma(vencido),
        'qtd_vencido': vencido.count(),
        'qtd_faturas': faturas.count(),
        'qtd_pagas': faturas.filter(status='pago').count(),
        'custo': custo,
        'margem': faturado - custo,
        'pct_recebido': int(recebido * 100 / faturado) if faturado else 0,
    }


def historico(meses=6):
    """Últimos N meses: faturado/recebido pelas faturas; custo do fechamento se houver, senão estimado."""
    hoje = timezone.localdate()
    ano, mes = hoje.year, hoje.month
    linhas = []
    for _ in range(meses):
        faturas = Invoice.objects.filter(ano_referencia=ano, mes_referencia=mes).exclude(status='cancelado')
        snaps = ContratoSnapshot.objects.filter(periodo__ano=ano, periodo__mes=mes)
        fechado = snaps.exists()
        custo = (snaps.aggregate(t=Sum('custo_total'))['t'] or ZERO) if fechado else custo_previsto(ano, mes)
        faturado = _soma(faturas)
        linhas.append({
            'rotulo': f'{MESES[mes]}/{str(ano)[2:]}', 'faturado': faturado, 'recebido': _soma(faturas.filter(status='pago')),
            'custo': custo, 'margem': faturado - custo, 'fechado': fechado,
        })
        ano, mes = mes_anterior(ano, mes)
    return linhas


def faturas_em_atraso():
    hoje = timezone.localdate()
    return Invoice.objects.filter(status__in=['pendente', 'atrasado'], vencimento__lt=hoje).select_related(
        'cliente').order_by('vencimento')


def agenda(dias=60, dias_passados=30):
    """
    Todas as datas que não podem passar, num lugar só: faturas, renovação de recursos,
    reajustes e fim de contrato. Itens vencidos (até `dias_passados`) vêm primeiro.
    """
    hoje = timezone.localdate()
    ate, desde = hoje + timedelta(days=dias), hoje - timedelta(days=dias_passados)
    eventos = []

    for f in Invoice.objects.filter(status__in=['pendente', 'atrasado'], vencimento__lte=ate).select_related('cliente'):
        eventos.append({
            'data': f.vencimento, 'tipo': 'fatura', 'titulo': f'Fatura {f.cliente.nome}',
            'detalhe': f'{brl(f.valor_total)} · {f.mes_referencia:02d}/{f.ano_referencia}',
            'obj': f, 'cliente_id': f.cliente_id,
        })
    for c in custos_monitorados(ate=ate).filter(vencimento__gte=desde):
        quem = 'cliente paga' if c.pago_pelo_cliente else brl(c.valor_total)
        eventos.append({
            'data': c.vencimento, 'tipo': 'recurso', 'titulo': f'Renovar {c.recurso}',
            'detalhe': f'{c.recurso.fornecedor} · {quem}', 'obj': c,
        })
    for r in ContratoReajuste.objects.filter(vigente_desde__gte=hoje, vigente_desde__lte=ate).select_related('contrato__cliente'):
        eventos.append({
            'data': r.vigente_desde, 'tipo': 'reajuste', 'titulo': f'Reajuste {r.contrato.cliente.nome}',
            'detalhe': f'{r.contrato.nome}: {brl(r.contrato.valor_em(r.vigente_desde - timedelta(days=1)))} → {brl(r.valor_mensal)}',
            'obj': r, 'cliente_id': r.contrato.cliente_id,
        })
    for c in Contrato.objects.filter(data_fim__gte=hoje, data_fim__lte=ate).select_related('cliente'):
        eventos.append({
            'data': c.data_fim, 'tipo': 'contrato', 'titulo': f'Fim do contrato {c.cliente.nome}',
            'detalhe': c.nome, 'obj': c, 'cliente_id': c.cliente_id,
        })

    for e in eventos:
        e['dias'] = (e['data'] - hoje).days
    eventos.sort(key=lambda e: (e['data'], e['tipo']))
    return eventos


def saude():
    """Coisas quebradas que impedem a cobrança automática de funcionar."""
    agora = timezone.now()
    abertas = Invoice.objects.filter(status__in=['pendente', 'atrasado'])
    itens = [
        ('Faturas em aberto sem link de pagamento',
         abertas.filter(Q(checkout_url='') | Q(checkout_url__isnull=True)).count(),
         'O job de checkouts tenta 2x por dia. Persistindo: conferir variáveis da InfinitePay.'),
        ('Faturas em aberto de cliente sem telefone',
         abertas.filter(Q(cliente__telefone__isnull=True) | Q(cliente__telefone='')).count(),
         'Sem telefone não sai lembrete no WhatsApp.'),
        ('Mensagens com erro de envio',
         MessageQueue.objects.filter(status='erro', agendado_para__gte=agora - timedelta(days=30)).count(),
         'Número inexistente no WhatsApp ou WAHA fora do ar.'),
        ('Mensagens paradas há mais de 1 dia',
         MessageQueue.objects.filter(status='pendente', agendado_para__lt=agora - timedelta(days=1)).count(),
         'A fila roda em dias úteis; fim de semana acumula.'),
    ]
    return [{'titulo': t, 'qtd': q, 'dica': d} for t, q, d in itens if q]
