from datetime import datetime, time
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from clientes.models import Cliente
from contratos.models import Contrato, ContratoReajuste
from infra.financeiro.models import ContratoSnapshot, DespesaAdicional, PeriodoFinanceiro
from infra.financeiro.services import fechar_periodo
from infra.recursos.models import CustoRecurso, Recurso, RecursoContrato
from infra.recursos.services import renovar
from invoices.models import Invoice, InvoiceContrato, MessageQueue
from invoices.services import invoice_service
from invoices.services.message_queue_service import _build_checkout_link
from invoices.tasks import task_enviar_confirmacao_imediata

from . import forms, services
from .templatetags.painel import brl

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url='/login/')


def _voltar(request, padrao):
    destino = request.POST.get('next') or request.GET.get('next')
    if destino and destino.startswith('/') and not destino.startswith('//'):
        return redirect(destino)
    return redirect(padrao)


# ---------- início ----------

@staff_required
def inicio(request):
    hoje = timezone.localdate()
    agenda = [e for e in services.agenda(dias=15, dias_passados=60) if e['tipo'] != 'fatura' or e['dias'] >= 0]
    return render(request, 'painel/inicio.html', {
        'resumo': services.resumo_mes(hoje.year, hoje.month),
        'atrasadas': services.faturas_em_atraso(),
        'agenda': agenda,
        'saude': services.saude(),
        'historico': services.historico(6),
    })


# ---------- cobranças ----------

def _faturas_do_mes(ano, mes):
    return Invoice.objects.filter(ano_referencia=ano, mes_referencia=mes).select_related('cliente').prefetch_related(
        Prefetch('itens_contrato', queryset=InvoiceContrato.objects.select_related('contrato'))
    ).order_by('vencimento', 'cliente__nome')


@staff_required
def cobrancas(request):
    ano, mes = forms.parse_mes(request.GET.get('mes'))
    primeiro = datetime(ano, mes, 1).date()
    faturados = set(InvoiceContrato.objects.filter(
        invoice__tipo='mensal', invoice__ano_referencia=ano, invoice__mes_referencia=mes,
    ).values_list('contrato_id', flat=True))
    a_gerar = [c for c in services.contratos_vigentes(primeiro) if c.id not in faturados and c.valor_em(primeiro) > 0]
    hoje = timezone.localdate()
    return render(request, 'painel/cobrancas.html', {
        'ano': ano, 'mes': mes,
        'mes_param': f'{ano}-{mes:02d}',
        'anterior': '%d-%02d' % services.mes_anterior(ano, mes),
        'seguinte': '%d-%02d' % services.mes_seguinte(ano, mes),
        'resumo': services.resumo_mes(ano, mes),
        'faturas': _faturas_do_mes(ano, mes),
        'atrasadas_antes': services.faturas_em_atraso().exclude(ano_referencia=ano, mes_referencia=mes),
        'a_gerar': a_gerar,
        'pode_gerar': (ano, mes) <= services.mes_seguinte(hoje.year, hoje.month),
    })


@staff_required
@require_POST
def gerar_mensalidades(request):
    ano, mes = forms.parse_mes(request.POST.get('mes'))
    r = invoice_service.gerar_invoices_mensais(mes=mes, ano=ano)
    if r['invoices_criados']:
        messages.success(request, f"{r['invoices_criados']} fatura(s) criada(s) para {mes:02d}/{ano}.")
    else:
        messages.info(request, 'Nada a gerar: todos os contratos do mês já têm fatura.')
    for erro in r['detalhes']['erros']:
        messages.error(request, f"{erro['cliente']}: {erro['erro']}")
    return redirect(f"{reverse('painel:cobrancas')}?mes={ano}-{mes:02d}")


@staff_required
def avulsa_nova(request):
    cliente = Cliente.objects.filter(pk=request.GET.get('cliente')).first()
    form = forms.AvulsaForm(request.POST or None, cliente=cliente,
                            initial={'vencimento': timezone.localdate()})
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        fatura = invoice_service.criar_avulsa(d['contrato'], d['descricao'], d['valor'], d['vencimento'])
        messages.success(request, f'Cobrança avulsa criada para {fatura.cliente.nome}.')
        return redirect('painel:fatura', pk=fatura.pk)
    return render(request, 'painel/form.html', {
        'form': form, 'titulo': 'Nova cobrança avulsa',
        'subtitulo': 'Horas extras, implantação, compra repassada... Gera link de pagamento e entra nos lembretes.',
        'voltar': reverse('painel:cobrancas'),
    })


def _render_linha(request, fatura):
    return render(request, 'painel/_fatura_linha.html', {'f': fatura})


@staff_required
@require_POST
def fatura_acao(request, pk, acao):
    fatura = get_object_or_404(Invoice.objects.select_related('cliente'), pk=pk)
    try:
        if acao == 'pagar':
            form = forms.PagamentoForm(request.POST)
            dia = form.cleaned_data['pago_em'] if form.is_valid() else timezone.localdate()
            pago_em = timezone.make_aware(datetime.combine(dia, time(12)))
            with transaction.atomic():
                mensagem = invoice_service.registrar_pagamento(fatura, pago_em=pago_em, capture_method='manual')
                if mensagem:
                    transaction.on_commit(lambda: task_enviar_confirmacao_imediata(mensagem.id), robust=True)
            messages.success(request, f'Pagamento registrado: {fatura.cliente.nome}. Confirmação enviada ao cliente.')
        elif acao == 'cancelar':
            invoice_service.cancelar_fatura(fatura)
            messages.success(request, f'Fatura de {fatura.cliente.nome} cancelada.')
        elif acao == 'lembrar':
            invoice_service.enviar_cobranca_agora(fatura)
            messages.success(request, f'Lembrete enviado no WhatsApp para {fatura.cliente.nome}.')
        elif acao == 'link':
            invoice_service.invalidar_checkout(fatura)
            ok = invoice_service.InfinitePayService().try_create_checkout(fatura)
            (messages.success if ok else messages.error)(
                request, 'Link de pagamento refeito.' if ok else 'InfinitePay não gerou o link; ver logs.')
        else:
            return redirect('painel:cobrancas')
    except Exception as exc:
        messages.error(request, f'Não deu: {exc}')
    fatura.refresh_from_db()
    if request.headers.get('HX-Request'):
        return _render_linha(request, fatura)
    return _voltar(request, reverse('painel:fatura', args=[fatura.pk]))


@staff_required
def fatura(request, pk):
    fatura = get_object_or_404(Invoice.objects.select_related('cliente'), pk=pk)
    form = forms.FaturaForm(request.POST or None, initial={'descricao': fatura.descricao, 'vencimento': fatura.vencimento})
    if request.method == 'POST' and fatura.em_aberto and form.is_valid():
        if form.cleaned_data['descricao'] != fatura.descricao:
            fatura.descricao = form.cleaned_data['descricao']
            fatura.save(update_fields=['descricao'])
        if form.cleaned_data['vencimento'] != fatura.vencimento:
            invoice_service.alterar_vencimento(fatura, form.cleaned_data['vencimento'])
        messages.success(request, 'Fatura atualizada.')
        return redirect('painel:fatura', pk=pk)
    return render(request, 'painel/fatura.html', {
        'f': fatura, 'form': form,
        'itens': fatura.itens_contrato.select_related('contrato'),
        'mensagens': fatura.mensagens.order_by('-agendado_para'),
        'link': _build_checkout_link(fatura),
        'pagamento_form': forms.PagamentoForm(),
    })


# ---------- clientes ----------

@staff_required
def clientes(request):
    hoje = timezone.localdate()
    primeiro = hoje.replace(day=1)
    vigentes = {}
    for c in services.contratos_vigentes(primeiro):
        vigentes.setdefault(c.cliente_id, []).append(c)
    em_aberto = dict(Invoice.objects.filter(status__in=['pendente', 'atrasado']).values('cliente').annotate(
        t=Sum('valor_total')).values_list('cliente', 't'))
    atrasado = dict(Invoice.objects.filter(status__in=['pendente', 'atrasado'], vencimento__lt=hoje).values(
        'cliente').annotate(t=Sum('valor_total')).values_list('cliente', 't'))
    linhas = []
    mostrar_inativos = request.GET.get('todos') == '1'
    for cli in Cliente.objects.all():
        if not cli.ativo and not mostrar_inativos:
            continue
        contratos = vigentes.get(cli.id, [])
        linhas.append({
            'c': cli, 'contratos': contratos,
            'mensal': sum((ct.valor_em(primeiro) for ct in contratos), Decimal('0')),
            'em_aberto': em_aberto.get(cli.id, 0), 'atrasado': atrasado.get(cli.id, 0),
        })
    return render(request, 'painel/clientes.html', {
        'linhas': linhas, 'mostrar_inativos': mostrar_inativos,
        'total_mensal': sum(l['mensal'] for l in linhas),
    })


@staff_required
def cliente_form(request, pk=None):
    cliente = get_object_or_404(Cliente, pk=pk) if pk else None
    form = forms.ClienteForm(request.POST or None, instance=cliente)
    if request.method == 'POST' and form.is_valid():
        cliente = form.save()
        messages.success(request, 'Cliente salvo.')
        return redirect('painel:cliente', pk=cliente.pk)
    return render(request, 'painel/form.html', {
        'form': form, 'titulo': f'Editar {cliente.nome}' if cliente else 'Novo cliente',
        'voltar': reverse('painel:cliente', args=[pk]) if pk else reverse('painel:clientes'),
    })


@staff_required
def cliente(request, pk):
    cli = get_object_or_404(Cliente, pk=pk)
    hoje = timezone.localdate()
    contratos = list(cli.contratos.prefetch_related(
        'reajustes', Prefetch('vinculos_recurso', queryset=RecursoContrato.objects.select_related('recurso'))
    ).order_by('data_fim', '-data_inicio'))
    for c in contratos:
        c.valor_hoje = c.valor_em(hoje.replace(day=1))
        c.encerrado = bool(c.data_fim and c.data_fim < hoje)
        c.reajustes_futuros = [r for r in c.reajustes.all() if r.vigente_desde > hoje]
    recursos_ids = RecursoContrato.objects.filter(contrato__cliente=cli).filter(
        Q(data_fim__isnull=True) | Q(data_fim__gte=hoje)).values_list('recurso_id', flat=True)
    recursos = []
    for r in Recurso.objects.filter(Q(id__in=recursos_ids) | Q(pai_id__in=recursos_ids)).distinct():
        r.custo = r.custo_atual()
        recursos.append(r)
    snaps = ContratoSnapshot.objects.filter(contrato__cliente=cli).values(
        'periodo__ano', 'periodo__mes').annotate(
        receita=Sum('receita'), custo=Sum('custo_total'), margem=Sum('margem')).order_by('-periodo__ano', '-periodo__mes')[:6]
    faturas = cli.invoices.order_by('-ano_referencia', '-mes_referencia', '-criado_em')
    return render(request, 'painel/cliente.html', {
        'c': cli, 'contratos': contratos, 'recursos': recursos, 'snaps': snaps,
        'faturas': faturas[:24], 'total_faturas': faturas.count(),
        'em_aberto': faturas.filter(status__in=['pendente', 'atrasado']).aggregate(t=Sum('valor_total'))['t'] or 0,
        'mensagens': MessageQueue.objects.filter(invoice__cliente=cli).select_related('invoice').order_by('-agendado_para')[:8],
        'reajuste_form': forms.ReajusteForm(), 'encerrar_form': forms.EncerrarForm(),
    })


# ---------- contratos ----------

@staff_required
def contrato_form(request, pk=None):
    contrato = get_object_or_404(Contrato, pk=pk) if pk else None
    inicial = {'cliente': request.GET.get('cliente'), 'data_inicio': timezone.localdate().replace(day=1)} if not pk else None
    form = forms.ContratoForm(request.POST or None, request.FILES or None, instance=contrato, initial=inicial)
    if request.method == 'POST' and form.is_valid():
        contrato = form.save()
        messages.success(request, 'Contrato salvo.')
        return redirect('painel:cliente', pk=contrato.cliente_id)
    cliente_id = contrato.cliente_id if contrato else request.GET.get('cliente')
    return render(request, 'painel/form.html', {
        'form': form, 'titulo': f'Editar contrato {contrato.nome}' if contrato else 'Novo contrato', 'multipart': True,
        'voltar': reverse('painel:cliente', args=[cliente_id]) if cliente_id else reverse('painel:clientes'),
    })


@staff_required
@require_POST
def contrato_reajuste(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk)
    form = forms.ReajusteForm(request.POST, instance=ContratoReajuste(contrato=contrato))
    if form.is_valid():
        r = form.save()
        messages.success(request, f'Reajuste: {brl(r.valor_mensal)} a partir de {r.vigente_desde:%m/%Y}.')
    else:
        messages.error(request, 'Reajuste inválido: ' + '; '.join(e for errs in form.errors.values() for e in errs))
    return redirect('painel:cliente', pk=contrato.cliente_id)


@staff_required
@require_POST
def reajuste_excluir(request, pk):
    r = get_object_or_404(ContratoReajuste, pk=pk, vigente_desde__gt=timezone.localdate())
    r.delete()
    messages.success(request, 'Reajuste removido.')
    return redirect('painel:cliente', pk=r.contrato.cliente_id)


@staff_required
@require_POST
def contrato_encerrar(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk)
    form = forms.EncerrarForm(request.POST)
    if form.is_valid():
        fim = form.cleaned_data['data_fim']
        with transaction.atomic():
            contrato.data_fim = fim
            contrato.save(update_fields=['data_fim'])
            n = contrato.vinculos_recurso.filter(Q(data_fim__isnull=True) | Q(data_fim__gt=fim)).update(data_fim=fim)
        messages.success(request, f'Contrato encerrado em {fim:%d/%m/%Y}' + (f'; {n} recurso(s) desvinculado(s).' if n else '.'))
    return redirect('painel:cliente', pk=contrato.cliente_id)


# ---------- agenda ----------

@staff_required
def agenda(request):
    try:
        dias = max(7, min(int(request.GET.get('dias', 60)), 400))
    except ValueError:
        dias = 60
    return render(request, 'painel/agenda.html', {'eventos': services.agenda(dias=dias), 'dias': dias, 'opcoes': (30, 60, 180, 365)})


# ---------- recursos ----------

@staff_required
def recursos(request):
    tipo = request.GET.get('tipo', '')
    qs = Recurso.objects.select_related('pai').prefetch_related(
        'custos', Prefetch('vinculos', queryset=RecursoContrato.objects.select_related('contrato__cliente')),
        Prefetch('pai__vinculos', queryset=RecursoContrato.objects.select_related('contrato__cliente')))
    if tipo:
        qs = qs.filter(tipo=tipo)
    if request.GET.get('todos') != '1':
        qs = qs.filter(ativo=True)
    hoje = timezone.localdate()
    linhas = []
    for r in qs:
        custos = [c for c in r.custos.all() if c.ativo and (c.data_fim is None or c.data_fim >= hoje)]
        custo = max(custos, key=lambda c: c.data_inicio, default=None)
        vinculos = r.vinculos.all() or (r.pai.vinculos.all() if r.pai else [])
        clientes = sorted({v.contrato.cliente.nome for v in vinculos if v.data_fim is None or v.data_fim >= hoje})
        linhas.append({'r': r, 'custo': custo, 'clientes': clientes,
                       'dias': (custo.vencimento - hoje).days if custo else None})
    linhas.sort(key=lambda l: (l['dias'] is None, l['dias'] if l['dias'] is not None else 0))
    total = sum((l['custo'].custo_mensal for l in linhas if l['custo'] and not l['custo'].pago_pelo_cliente), Decimal('0'))
    return render(request, 'painel/recursos.html', {
        'linhas': linhas, 'tipo': tipo, 'tipos': Recurso.TIPO_CHOICES, 'total_mensal': total,
        'todos': request.GET.get('todos') == '1',
    })


@staff_required
def recurso_form(request, pk=None):
    recurso = get_object_or_404(Recurso, pk=pk) if pk else None
    form = forms.RecursoForm(request.POST or None, instance=recurso, initial={'tipo': request.GET.get('tipo')})
    custo_form = None if recurso else forms.CustoForm(request.POST or None, prefix='custo', initial={
        'periodo_meses': 12, 'data_inicio': timezone.localdate()})
    if request.method == 'POST' and form.is_valid() and (custo_form is None or custo_form.is_valid()):
        with transaction.atomic():
            recurso = form.save()
            if custo_form is not None:
                custo = custo_form.save(commit=False)
                custo.recurso = recurso
                custo.save()
        messages.success(request, 'Recurso salvo.')
        return redirect('painel:recurso', pk=recurso.pk)
    return render(request, 'painel/form.html', {
        'form': form, 'form2': custo_form, 'form2_titulo': 'Custo e renovação',
        'titulo': f'Editar {recurso}' if recurso else 'Novo recurso',
        'subtitulo': None if recurso else 'Domínio, VPS, hosting, e-mail, certificado, licença... tudo que vence e precisa renovar.',
        'voltar': reverse('painel:recurso', args=[pk]) if pk else reverse('painel:recursos'),
    })


@staff_required
def recurso(request, pk):
    r = get_object_or_404(Recurso.objects.select_related('pai'), pk=pk)
    custo_form = forms.CustoForm(prefix='custo', initial={'periodo_meses': 12, 'data_inicio': timezone.localdate()})
    vinculo_form = forms.VinculoForm(prefix='vinculo')
    if request.method == 'POST':
        if 'custo-valor_total' in request.POST:
            custo_form = forms.CustoForm(request.POST, prefix='custo', instance=CustoRecurso(recurso=r))
            if custo_form.is_valid():
                custo_form.save()
                messages.success(request, 'Custo adicionado.')
                return redirect('painel:recurso', pk=pk)
        else:
            vinculo_form = forms.VinculoForm(request.POST, prefix='vinculo', instance=RecursoContrato(recurso=r))
            if vinculo_form.is_valid():
                vinculo_form.save()
                messages.success(request, 'Contrato vinculado.')
                return redirect('painel:recurso', pk=pk)
    return render(request, 'painel/recurso.html', {
        'r': r, 'custos': r.custos.all(), 'filhos': r.filhos.all(),
        'vinculos': r.vinculos.select_related('contrato__cliente'),
        'custo_form': custo_form, 'vinculo_form': vinculo_form, 'hoje': timezone.localdate(),
    })


@staff_required
def custo_editar(request, pk):
    custo = get_object_or_404(CustoRecurso.objects.select_related('recurso'), pk=pk)
    form = forms.CustoForm(request.POST or None, instance=custo)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Custo atualizado.')
        return redirect('painel:recurso', pk=custo.recurso_id)
    return render(request, 'painel/form.html', {
        'form': form, 'titulo': f'Custo de {custo.recurso}',
        'subtitulo': 'Já entrou em mês fechado? Valor não muda: encerre (campo "Até") e crie outro custo.',
        'voltar': reverse('painel:recurso', args=[custo.recurso_id]),
    })


@staff_required
@require_POST
def custo_renovar(request, pk):
    custo = renovar(get_object_or_404(CustoRecurso.objects.select_related('recurso'), pk=pk))
    messages.success(request, f'{custo.recurso} renovado: próximo vencimento {custo.vencimento:%d/%m/%Y}.')
    return _voltar(request, reverse('painel:recurso', args=[custo.recurso_id]))


@staff_required
@require_POST
def vinculo_encerrar(request, pk):
    v = get_object_or_404(RecursoContrato, pk=pk)
    v.data_fim = timezone.localdate()
    if v.data_fim < v.data_inicio:
        v.delete()
    else:
        v.save(update_fields=['data_fim'])
    messages.success(request, 'Vínculo encerrado.')
    return redirect('painel:recurso', pk=v.recurso_id)


# ---------- financeiro ----------

@staff_required
def financeiro(request):
    hoje = timezone.localdate()
    periodos = []
    for p in PeriodoFinanceiro.objects.all()[:24]:
        t = p.contrato_snapshots.aggregate(receita=Sum('receita'), custo=Sum('custo_total'), margem=Sum('margem'))
        periodos.append({'p': p, **t})
    ano, mes = services.mes_anterior(hoje.year, hoje.month)
    anterior_aberto = not PeriodoFinanceiro.objects.filter(ano=ano, mes=mes, fechado=True).exists()
    return render(request, 'painel/financeiro.html', {
        'periodos': periodos, 'atual': services.resumo_mes(hoje.year, hoje.month),
        'anterior': (ano, mes) if anterior_aberto else None,
    })


@staff_required
def periodo(request, ano, mes):
    p = PeriodoFinanceiro.objects.filter(ano=ano, mes=mes).first()
    form = forms.DespesaForm(request.POST or None)
    if request.method == 'POST':
        if p and p.fechado:
            messages.error(request, 'Período fechado: não aceita despesas.')
        elif form.is_valid():
            despesa = form.save(commit=False)
            despesa.mes_referencia, despesa.ano_referencia = mes, ano
            despesa.criado_por = request.user.get_username()
            despesa.save()
            messages.success(request, 'Despesa lançada.')
            return redirect('painel:periodo', ano=ano, mes=mes)
    snaps = p.contrato_snapshots.select_related('contrato__cliente').order_by('-margem') if p else []
    return render(request, 'painel/periodo.html', {
        'p': p, 'ano': ano, 'mes': mes, 'rotulo': f'{services.MESES[mes]}/{ano}',
        'snaps': snaps, 'resumo': services.resumo_mes(ano, mes),
        'despesas': DespesaAdicional.objects.filter(ano_referencia=ano, mes_referencia=mes).select_related('contrato__cliente'),
        'form': form,
        'pode_fechar': (not p or not p.fechado) and (ano, mes) < (timezone.localdate().year, timezone.localdate().month),
    })


@staff_required
@require_POST
def periodo_fechar(request, ano, mes):
    p, _ = PeriodoFinanceiro.objects.get_or_create(ano=ano, mes=mes)
    try:
        r = fechar_periodo(p.id, request.user.get_username())
        messages.success(request, f"{mes:02d}/{ano} fechado: {r['contratos_processados']} contratos, margem {brl(r['margem_total'])}.")
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('painel:periodo', ano=ano, mes=mes)
