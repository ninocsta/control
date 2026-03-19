import calendar
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Sum
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import (
    CategoriaDespesaSalao,
    ComissaoMensalSalao,
    DespesaSalao,
    LancamentoSalao,
    ServicoSalao,
)


MONTH_OPTIONS = [(m, f"{m:02d}") for m in range(1, 13)]


def _salao_superuser_required(view_func):
    return user_passes_test(
        lambda user: user.is_authenticated and user.is_superuser,
        login_url='/admin/login/',
    )(view_func)


def _normalize_codigo(value: str) -> str:
    return (value or '').strip().upper()


def _parse_competencia(request):
    today = date.today()
    raw_ano = request.POST.get('ano') or request.GET.get('ano')
    raw_mes = request.POST.get('mes') or request.GET.get('mes')

    try:
        ano = int(raw_ano) if raw_ano else today.year
    except (TypeError, ValueError):
        ano = today.year

    try:
        mes = int(raw_mes) if raw_mes else today.month
    except (TypeError, ValueError):
        mes = today.month

    if mes < 1 or mes > 12:
        mes = today.month

    if ano < 2000 or ano > 2100:
        ano = today.year

    return ano, mes


def _parse_day(request, ano, mes, clamp_on_overflow=False):
    raw_dia = request.POST.get('dia') or request.GET.get('dia')
    if raw_dia is None or raw_dia == '':
        return min(date.today().day, calendar.monthrange(ano, mes)[1])

    try:
        dia = int(raw_dia)
    except (TypeError, ValueError):
        return None

    ultimo_dia = calendar.monthrange(ano, mes)[1]
    if clamp_on_overflow and dia > ultimo_dia:
        return ultimo_dia

    if clamp_on_overflow and dia < 1:
        return 1

    if dia < 1 or dia > ultimo_dia:
        return None

    return dia


def _parse_decimal(raw_value):
    normalized = (raw_value or '').strip().replace(',', '.')
    if not normalized:
        return None
    try:
        value = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _parse_checkbox(raw_value):
    return raw_value in ('on', '1', 'true', 'True')


def _redirect_lancamentos(ano, mes, dia):
    return redirect(f"{reverse('salao:lancamentos')}?ano={ano}&mes={mes}&dia={dia}")


def _redirect_despesas(ano, mes):
    return redirect(f"{reverse('salao:despesas')}?ano={ano}&mes={mes}")


def _redirect_dashboard(ano, mes):
    return redirect(f"{reverse('salao:dashboard')}?ano={ano}&mes={mes}")


def _redirect_servicos():
    return redirect(reverse('salao:servicos'))


def _redirect_categorias():
    return redirect(reverse('salao:categorias'))


def _date_range_for_month(ano, mes):
    start = date(ano, mes, 1)
    end = date(ano, mes, calendar.monthrange(ano, mes)[1])
    return start, end


def _iter_months_backwards(ano, mes, quantidade):
    meses = []
    ano_cursor = ano
    mes_cursor = mes
    for _ in range(quantidade):
        meses.append((ano_cursor, mes_cursor))
        mes_cursor -= 1
        if mes_cursor == 0:
            mes_cursor = 12
            ano_cursor -= 1
    meses.reverse()
    return meses


def _build_year_options():
    current = date.today().year
    return [current - 1, current, current + 1, current + 2]


def _resumo_lancamentos_por_competencia(ano, mes, dia):
    inicio_mes, fim_mes = _date_range_for_month(ano, mes)
    data_fixa = date(ano, mes, dia)

    resumo_dia_qs = LancamentoSalao.objects.filter(data=data_fixa)
    resumo_mes_qs = LancamentoSalao.objects.filter(data__range=(inicio_mes, fim_mes))

    resumo_dia = {
        'qtd': resumo_dia_qs.count(),
        'total': resumo_dia_qs.aggregate(total=Sum('valor_cobrado'))['total'] or Decimal('0.00'),
    }
    resumo_mes = {
        'qtd': resumo_mes_qs.count(),
        'total': resumo_mes_qs.aggregate(total=Sum('valor_cobrado'))['total'] or Decimal('0.00'),
    }

    return resumo_dia, resumo_mes, inicio_mes, fim_mes, data_fixa


@_salao_superuser_required
def index(request):
    return redirect('salao:dashboard')


@_salao_superuser_required
def lancamentos(request):
    ano, mes = _parse_competencia(request)
    dia = _parse_day(request, ano, mes, clamp_on_overflow=(request.method == 'GET'))
    if dia is None:
        messages.error(request, 'Dia inválido para a competência selecionada.')
        dia = min(date.today().day, calendar.monthrange(ano, mes)[1])

    if request.GET.get('resumo') == '1':
        resumo_dia, resumo_mes, *_ = _resumo_lancamentos_por_competencia(ano, mes, dia)
        return JsonResponse(
            {
                'ano': ano,
                'mes': mes,
                'dia': dia,
                'resumo_dia': {
                    'qtd': resumo_dia['qtd'],
                    'total': float(resumo_dia['total']),
                },
                'resumo_mes': {
                    'qtd': resumo_mes['qtd'],
                    'total': float(resumo_mes['total']),
                },
            }
        )

    servicos_ativos = list(ServicoSalao.objects.filter(ativo=True).order_by('ordem', 'codigo'))

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_lancamento':
            codigo = _normalize_codigo(request.POST.get('codigo'))
            valor = _parse_decimal(request.POST.get('valor_cobrado'))
            dia_post = _parse_day(request, ano, mes, clamp_on_overflow=False)

            if dia_post is None:
                messages.error(request, 'Dia inválido.')
                return _redirect_lancamentos(ano, mes, dia)

            if not codigo:
                messages.error(request, 'Informe o código do serviço.')
                return _redirect_lancamentos(ano, mes, dia_post)

            servico = ServicoSalao.objects.filter(codigo=codigo, ativo=True).first()
            if not servico:
                messages.error(request, f"Código '{codigo}' não encontrado entre os serviços ativos.")
                return _redirect_lancamentos(ano, mes, dia_post)

            if valor is None or valor < Decimal('0.00'):
                messages.error(request, 'Informe um valor válido.')
                return _redirect_lancamentos(ano, mes, dia_post)

            LancamentoSalao.objects.create(
                data=date(ano, mes, dia_post),
                servico=servico,
                valor_cobrado=valor,
            )
            messages.success(request, 'Lançamento salvo com sucesso.')
            return _redirect_lancamentos(ano, mes, dia_post)

        if action == 'delete_lancamento':
            lancamento_id = request.POST.get('lancamento_id')
            lancamento = get_object_or_404(LancamentoSalao, id=lancamento_id)
            lancamento.delete()
            messages.success(request, 'Lançamento removido com sucesso.')
            return _redirect_lancamentos(ano, mes, dia)

        if action == 'update_lancamento':
            lancamento_id = request.POST.get('lancamento_id')
            lancamento = get_object_or_404(LancamentoSalao, id=lancamento_id)

            raw_data = request.POST.get('data')
            try:
                ano_edit, mes_edit, dia_edit = [int(part) for part in raw_data.split('-')]
                data_editada = date(ano_edit, mes_edit, dia_edit)
            except (TypeError, ValueError, AttributeError):
                messages.error(request, 'Data inválida para edição do lançamento.')
                return _redirect_lancamentos(ano, mes, dia)

            servico_id = request.POST.get('servico_id')
            servico = ServicoSalao.objects.filter(id=servico_id, ativo=True).first()
            if not servico:
                messages.error(request, 'Selecione um serviço ativo válido para edição.')
                return _redirect_lancamentos(ano, mes, dia)

            valor = _parse_decimal(request.POST.get('valor_cobrado'))
            if valor is None or valor < Decimal('0.00'):
                messages.error(request, 'Informe um valor válido para edição.')
                return _redirect_lancamentos(ano, mes, dia)

            lancamento.data = data_editada
            lancamento.servico = servico
            lancamento.valor_cobrado = valor
            lancamento.save(update_fields=['data', 'servico', 'valor_cobrado', 'atualizado_em'])
            messages.success(request, 'Lançamento atualizado com sucesso.')
            return _redirect_lancamentos(ano, mes, dia)

    resumo_dia, resumo_mes, inicio_mes, fim_mes, data_fixa = _resumo_lancamentos_por_competencia(ano, mes, dia)

    lancamentos_mes = (
        LancamentoSalao.objects.filter(data__range=(inicio_mes, fim_mes))
        .select_related('servico')
        .order_by('-data', '-id')[:120]
    )

    lancamentos_dia = (
        LancamentoSalao.objects.filter(data=data_fixa)
        .select_related('servico')
        .order_by('-id')[:30]
    )

    edit_lancamento = None
    edit_lancamento_id = request.GET.get('edit')
    if edit_lancamento_id:
        edit_lancamento = LancamentoSalao.objects.filter(id=edit_lancamento_id).select_related('servico').first()

    context = {
        'active_tab': 'lancamentos',
        'ano': ano,
        'mes': mes,
        'dia': dia,
        'month_options': MONTH_OPTIONS,
        'year_options': _build_year_options(),
        'servicos_ativos': servicos_ativos,
        'servicos_catalogo': [
            {
                'id': servico.id,
                'codigo': servico.codigo,
                'nome': servico.nome,
                'valor_padrao': str(servico.valor_padrao),
            }
            for servico in servicos_ativos
        ],
        'lancamentos_mes': lancamentos_mes,
        'lancamentos_dia': lancamentos_dia,
        'edit_lancamento': edit_lancamento,
        'resumo_dia': resumo_dia,
        'resumo_mes': resumo_mes,
    }
    return render(request, 'salao/lancamentos.html', context)


@_salao_superuser_required
def despesas(request):
    ano, mes = _parse_competencia(request)
    categorias_ativas = list(
        CategoriaDespesaSalao.objects.filter(ativo=True).order_by('ordem', 'nome')
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_despesa':
            raw_data = request.POST.get('data')
            try:
                ano_d, mes_d, dia_d = [int(part) for part in raw_data.split('-')]
                data_despesa = date(ano_d, mes_d, dia_d)
            except (TypeError, ValueError, AttributeError):
                messages.error(request, 'Data inválida.')
                return _redirect_despesas(ano, mes)

            categoria_id = request.POST.get('categoria_id')
            categoria = CategoriaDespesaSalao.objects.filter(id=categoria_id, ativo=True).first()
            if not categoria:
                messages.error(request, 'Selecione uma categoria ativa.')
                return _redirect_despesas(ano, mes)

            valor = _parse_decimal(request.POST.get('valor'))
            if valor is None or valor < Decimal('0.00'):
                messages.error(request, 'Informe um valor válido.')
                return _redirect_despesas(ano, mes)

            observacao = (request.POST.get('observacao') or '').strip()

            DespesaSalao.objects.create(
                data=data_despesa,
                categoria=categoria,
                valor=valor,
                observacao=observacao,
            )
            messages.success(request, 'Despesa salva com sucesso.')
            return _redirect_despesas(ano, mes)

        if action == 'delete_despesa':
            despesa_id = request.POST.get('despesa_id')
            despesa = get_object_or_404(DespesaSalao, id=despesa_id)
            despesa.delete()
            messages.success(request, 'Despesa removida com sucesso.')
            return _redirect_despesas(ano, mes)

        if action == 'update_despesa':
            despesa_id = request.POST.get('despesa_id')
            despesa = get_object_or_404(DespesaSalao, id=despesa_id)

            raw_data = request.POST.get('data')
            try:
                ano_d, mes_d, dia_d = [int(part) for part in raw_data.split('-')]
                data_editada = date(ano_d, mes_d, dia_d)
            except (TypeError, ValueError, AttributeError):
                messages.error(request, 'Data inválida para edição.')
                return _redirect_despesas(ano, mes)

            categoria_id = request.POST.get('categoria_id')
            categoria = CategoriaDespesaSalao.objects.filter(id=categoria_id, ativo=True).first()
            if not categoria:
                messages.error(request, 'Selecione uma categoria ativa válida.')
                return _redirect_despesas(ano, mes)

            valor = _parse_decimal(request.POST.get('valor'))
            if valor is None or valor < Decimal('0.00'):
                messages.error(request, 'Informe um valor válido para edição.')
                return _redirect_despesas(ano, mes)

            despesa.data = data_editada
            despesa.categoria = categoria
            despesa.valor = valor
            despesa.observacao = (request.POST.get('observacao') or '').strip()
            despesa.save(update_fields=['data', 'categoria', 'valor', 'observacao', 'atualizado_em'])
            messages.success(request, 'Despesa atualizada com sucesso.')
            return _redirect_despesas(ano, mes)

    inicio_mes, fim_mes = _date_range_for_month(ano, mes)
    despesas_mes = (
        DespesaSalao.objects.filter(data__range=(inicio_mes, fim_mes))
        .select_related('categoria')
        .order_by('-data', '-id')[:150]
    )

    edit_despesa = None
    edit_despesa_id = request.GET.get('edit')
    if edit_despesa_id:
        edit_despesa = DespesaSalao.objects.filter(id=edit_despesa_id).select_related('categoria').first()

    context = {
        'active_tab': 'despesas',
        'ano': ano,
        'mes': mes,
        'month_options': MONTH_OPTIONS,
        'year_options': _build_year_options(),
        'categorias_ativas': categorias_ativas,
        'despesas_mes': despesas_mes,
        'edit_despesa': edit_despesa,
        'data_padrao': date(ano, mes, min(date.today().day, calendar.monthrange(ano, mes)[1])),
    }
    return render(request, 'salao/despesas.html', context)


@_salao_superuser_required
def servicos(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_servico':
            codigo = _normalize_codigo(request.POST.get('codigo'))
            nome = (request.POST.get('nome') or '').strip()
            valor_padrao = _parse_decimal(request.POST.get('valor_padrao'))
            ordem = request.POST.get('ordem') or '0'
            ativo = _parse_checkbox(request.POST.get('ativo'))

            try:
                ordem = int(ordem)
            except (TypeError, ValueError):
                ordem = 0

            if not codigo or not nome or valor_padrao is None:
                messages.error(request, 'Preencha código, nome e valor padrão válidos.')
                return _redirect_servicos()

            if ServicoSalao.objects.filter(codigo=codigo).exists():
                messages.error(request, f'Já existe serviço com código {codigo}.')
                return _redirect_servicos()

            ServicoSalao.objects.create(
                codigo=codigo,
                nome=nome,
                valor_padrao=valor_padrao,
                ordem=ordem,
                ativo=ativo,
            )
            messages.success(request, 'Serviço criado com sucesso.')
            return _redirect_servicos()

        if action == 'update_servico':
            servico_id = request.POST.get('servico_id')
            servico = get_object_or_404(ServicoSalao, id=servico_id)

            codigo = _normalize_codigo(request.POST.get('codigo'))
            nome = (request.POST.get('nome') or '').strip()
            valor_padrao = _parse_decimal(request.POST.get('valor_padrao'))
            ordem = request.POST.get('ordem') or '0'
            ativo = _parse_checkbox(request.POST.get('ativo'))

            try:
                ordem = int(ordem)
            except (TypeError, ValueError):
                ordem = 0

            if not codigo or not nome or valor_padrao is None:
                messages.error(request, 'Preencha código, nome e valor padrão válidos.')
                return _redirect_servicos()

            if ServicoSalao.objects.exclude(id=servico.id).filter(codigo=codigo).exists():
                messages.error(request, f'Já existe outro serviço com código {codigo}.')
                return _redirect_servicos()

            servico.codigo = codigo
            servico.nome = nome
            servico.valor_padrao = valor_padrao
            servico.ordem = ordem
            servico.ativo = ativo
            servico.save()
            messages.success(request, 'Serviço atualizado com sucesso.')
            return _redirect_servicos()

        if action == 'delete_servico':
            servico_id = request.POST.get('servico_id')
            servico = get_object_or_404(ServicoSalao, id=servico_id)
            try:
                servico.delete()
                messages.success(request, 'Serviço removido com sucesso.')
            except ProtectedError:
                messages.error(
                    request,
                    'Não foi possível remover: esse serviço possui lançamentos vinculados.',
                )
            return _redirect_servicos()

    servicos_qs = ServicoSalao.objects.all().order_by('ordem', 'codigo')
    edit_id = request.GET.get('edit')
    edit_servico = ServicoSalao.objects.filter(id=edit_id).first() if edit_id else None

    context = {
        'active_tab': 'servicos',
        'servicos': servicos_qs,
        'edit_servico': edit_servico,
    }
    return render(request, 'salao/servicos.html', context)


@_salao_superuser_required
def categorias(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_categoria':
            nome = (request.POST.get('nome') or '').strip()
            ordem = request.POST.get('ordem') or '0'
            ativo = _parse_checkbox(request.POST.get('ativo'))

            try:
                ordem = int(ordem)
            except (TypeError, ValueError):
                ordem = 0

            if not nome:
                messages.error(request, 'Informe o nome da categoria.')
                return _redirect_categorias()

            if CategoriaDespesaSalao.objects.filter(nome__iexact=nome).exists():
                messages.error(request, f'Categoria "{nome}" já existe.')
                return _redirect_categorias()

            CategoriaDespesaSalao.objects.create(
                nome=nome,
                ordem=ordem,
                ativo=ativo,
            )
            messages.success(request, 'Categoria criada com sucesso.')
            return _redirect_categorias()

        if action == 'update_categoria':
            categoria_id = request.POST.get('categoria_id')
            categoria = get_object_or_404(CategoriaDespesaSalao, id=categoria_id)

            nome = (request.POST.get('nome') or '').strip()
            ordem = request.POST.get('ordem') or '0'
            ativo = _parse_checkbox(request.POST.get('ativo'))

            try:
                ordem = int(ordem)
            except (TypeError, ValueError):
                ordem = 0

            if not nome:
                messages.error(request, 'Informe o nome da categoria.')
                return _redirect_categorias()

            if CategoriaDespesaSalao.objects.exclude(id=categoria.id).filter(nome__iexact=nome).exists():
                messages.error(request, f'Categoria "{nome}" já existe.')
                return _redirect_categorias()

            categoria.nome = nome
            categoria.ordem = ordem
            categoria.ativo = ativo
            categoria.save()
            messages.success(request, 'Categoria atualizada com sucesso.')
            return _redirect_categorias()

        if action == 'delete_categoria':
            categoria_id = request.POST.get('categoria_id')
            categoria = get_object_or_404(CategoriaDespesaSalao, id=categoria_id)
            try:
                categoria.delete()
                messages.success(request, 'Categoria removida com sucesso.')
            except ProtectedError:
                messages.error(
                    request,
                    'Não foi possível remover: essa categoria possui despesas vinculadas.',
                )
            return _redirect_categorias()

    categorias_qs = CategoriaDespesaSalao.objects.all().order_by('ordem', 'nome')
    edit_id = request.GET.get('edit')
    edit_categoria = CategoriaDespesaSalao.objects.filter(id=edit_id).first() if edit_id else None

    context = {
        'active_tab': 'categorias',
        'categorias': categorias_qs,
        'edit_categoria': edit_categoria,
    }
    return render(request, 'salao/categorias.html', context)


@_salao_superuser_required
def dashboard(request):
    ano, mes = _parse_competencia(request)

    comissao, _ = ComissaoMensalSalao.objects.get_or_create(
        ano=ano,
        mes=mes,
        defaults={'percentual': Decimal('20.00')},
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_meta':
            raw_meta = (request.POST.get('meta_faturamento') or '').strip()
            if raw_meta == '':
                comissao.meta_faturamento = None
                comissao.save(update_fields=['meta_faturamento', 'updated_at'])
                messages.success(request, 'Meta mensal removida.')
                return _redirect_dashboard(ano, mes)

            meta_value = _parse_decimal(raw_meta)
            if meta_value is None or meta_value < Decimal('0.00'):
                messages.error(request, 'Informe uma meta mensal válida.')
                return _redirect_dashboard(ano, mes)

            comissao.meta_faturamento = meta_value
            comissao.save(update_fields=['meta_faturamento', 'updated_at'])
            messages.success(request, 'Meta mensal atualizada.')
            return _redirect_dashboard(ano, mes)

    lancamentos_mes = LancamentoSalao.objects.filter(data__year=ano, data__month=mes)
    despesas_mes = DespesaSalao.objects.filter(data__year=ano, data__month=mes)

    faturamento_bruto = lancamentos_mes.aggregate(total=Sum('valor_cobrado'))['total'] or Decimal('0.00')
    despesas_total = despesas_mes.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    atendimentos_total = lancamentos_mes.count()
    ticket_medio = (
        (faturamento_bruto / Decimal(atendimentos_total)).quantize(Decimal('0.01'))
        if atendimentos_total > 0
        else Decimal('0.00')
    )

    comissao_calculada = (
        (faturamento_bruto * comissao.percentual) / Decimal('100.00')
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    comissao_paga = comissao_calculada
    valor_pos_comissao = faturamento_bruto - comissao_paga
    lucro = valor_pos_comissao - despesas_total

    meta_faturamento = comissao.meta_faturamento
    percentual_meta_atingido = None
    valor_faltante_meta = None
    if meta_faturamento and meta_faturamento > Decimal('0.00'):
        percentual_meta_atingido = (
            (faturamento_bruto / meta_faturamento) * Decimal('100.00')
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        valor_faltante_meta = max(
            (meta_faturamento - faturamento_bruto).quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP,
            ),
            Decimal('0.00'),
        )

    ranking_servicos = (
        lancamentos_mes.values('servico__codigo', 'servico__nome')
        .annotate(quantidade=Count('id'), total=Sum('valor_cobrado'))
        .order_by('-quantidade', '-total', 'servico__codigo')
    )

    despesas_por_categoria = (
        despesas_mes.values('categoria__nome')
        .annotate(total=Sum('valor'))
        .order_by('-total', 'categoria__nome')
    )

    serie_meses = _iter_months_backwards(ano, mes, quantidade=6)
    existing_commissions = {
        (item.ano, item.mes): item.percentual
        for item in ComissaoMensalSalao.objects.filter(
            ano__in={item_ano for item_ano, _ in serie_meses}
        )
    }

    chart_labels = []
    chart_faturamento = []
    chart_despesas = []
    chart_lucro = []
    chart_atendimentos = []
    chart_ticket = []

    for ano_item, mes_item in serie_meses:
        label = f"{mes_item:02d}/{ano_item}"
        lancamentos_item = LancamentoSalao.objects.filter(data__year=ano_item, data__month=mes_item)
        despesas_item = DespesaSalao.objects.filter(data__year=ano_item, data__month=mes_item)

        faturamento_item = lancamentos_item.aggregate(total=Sum('valor_cobrado'))['total'] or Decimal('0.00')
        despesas_item_total = despesas_item.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        percentual_item = existing_commissions.get((ano_item, mes_item), Decimal('20.00'))
        comissao_item = (faturamento_item * percentual_item / Decimal('100.00')).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP,
        )
        lucro_item = faturamento_item - comissao_item - despesas_item_total
        qtd_item = lancamentos_item.count()
        ticket_item = (
            (faturamento_item / Decimal(qtd_item)).quantize(Decimal('0.01'))
            if qtd_item > 0
            else Decimal('0.00')
        )

        chart_labels.append(label)
        chart_faturamento.append(float(faturamento_item))
        chart_despesas.append(float(despesas_item_total))
        chart_lucro.append(float(lucro_item))
        chart_atendimentos.append(qtd_item)
        chart_ticket.append(float(ticket_item))

    atendimentos_por_dia_qs = (
        lancamentos_mes.values('data__day')
        .annotate(qtd=Count('id'), total=Sum('valor_cobrado'))
        .order_by('data__day')
    )
    map_qtd_por_dia = {item['data__day']: item['qtd'] for item in atendimentos_por_dia_qs}
    map_total_por_dia = {item['data__day']: float(item['total'] or 0) for item in atendimentos_por_dia_qs}
    dias_mes_chart = calendar.monthrange(ano, mes)[1]
    dias_labels = [f"{dia:02d}" for dia in range(1, dias_mes_chart + 1)]
    dias_qtd = [map_qtd_por_dia.get(dia, 0) for dia in range(1, dias_mes_chart + 1)]
    dias_total = [map_total_por_dia.get(dia, 0.0) for dia in range(1, dias_mes_chart + 1)]

    context = {
        'active_tab': 'dashboard',
        'ano': ano,
        'mes': mes,
        'month_options': MONTH_OPTIONS,
        'year_options': _build_year_options(),
        'faturamento_bruto': faturamento_bruto,
        'comissao_percentual': comissao.percentual,
        'comissao_calculada': comissao_calculada,
        'comissao_paga': comissao_paga,
        'valor_pos_comissao': valor_pos_comissao,
        'despesas_total': despesas_total,
        'lucro': lucro,
        'meta_faturamento': meta_faturamento,
        'percentual_meta_atingido': percentual_meta_atingido,
        'valor_faltante_meta': valor_faltante_meta,
        'atendimentos_total': atendimentos_total,
        'ticket_medio': ticket_medio,
        'ranking_servicos': ranking_servicos,
        'despesas_por_categoria': despesas_por_categoria,
        'comparativo_chart': {
            'labels': chart_labels,
            'faturamento': chart_faturamento,
            'despesas': chart_despesas,
            'lucro': chart_lucro,
        },
        'operacao_chart': {
            'labels': chart_labels,
            'atendimentos': chart_atendimentos,
            'ticket_medio': chart_ticket,
        },
        'atendimentos_dia_chart': {
            'labels': dias_labels,
            'atendimentos': dias_qtd,
            'faturamento': dias_total,
        },
    }
    return render(request, 'salao/dashboard.html', context)
