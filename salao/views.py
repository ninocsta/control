import calendar
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from .models import (
    CategoriaDespesaSalao,
    ComissaoMensalSalao,
    DespesaSalao,
    FormaPagamentoSalao,
    LancamentoSalao,
    ServicoSalao,
    TaxaFormaPagamentoSalao,
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


def _parse_int_in_range(raw_value, default, min_value, max_value):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    if value < min_value or value > max_value:
        return default
    return value


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


def _redirect_pagamentos(forma_taxa_id=None):
    if forma_taxa_id:
        return redirect(f"{reverse('salao:pagamentos')}?forma_taxa={forma_taxa_id}")
    return redirect(reverse('salao:pagamentos'))


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


def _add_months_preserving_day(base_date, months_to_add):
    base_month_index = (base_date.month - 1) + months_to_add
    year = base_date.year + (base_month_index // 12)
    month = (base_month_index % 12) + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _split_amount_evenly(total, parcelas):
    parcela_base = (total / Decimal(parcelas)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    valores = [parcela_base for _ in range(parcelas)]
    diferenca = total - sum(valores)
    if diferenca != Decimal('0.00'):
        valores[-1] = (valores[-1] + diferenca).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return valores


def _parse_parcelas(raw_value, default=1):
    return _parse_int_in_range(raw_value, default=default, min_value=1, max_value=12)


def _build_formas_catalogo(formas):
    taxas_qs = TaxaFormaPagamentoSalao.objects.select_related('forma_pagamento').filter(
        forma_pagamento__in=formas
    )
    taxas_por_forma = {}
    for taxa in taxas_qs:
        taxas_por_forma.setdefault(taxa.forma_pagamento_id, {})[str(taxa.parcelas)] = str(taxa.percentual)

    catalogo = []
    for forma in formas:
        catalogo.append(
            {
                'id': forma.id,
                'codigo': forma.codigo,
                'nome': forma.nome,
                'aceita_parcelamento': forma.aceita_parcelamento,
                'taxas': taxas_por_forma.get(forma.id, {}),
            }
        )
    return catalogo


def _calcular_liquido_com_taxa(valor_bruto, percentual):
    valor_taxa = (valor_bruto * percentual / Decimal('100.00')).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP,
    )
    valor_liquido = (valor_bruto - valor_taxa).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if valor_liquido < Decimal('0.00'):
        valor_liquido = Decimal('0.00')
    return valor_taxa, valor_liquido


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

    servicos_ativos = list(ServicoSalao.objects.filter(ativo=True).order_by('codigo'))
    formas_pagamento_ativas = list(FormaPagamentoSalao.objects.filter(ativo=True).order_by('codigo'))

    if request.GET.get('resumo') == '1' or request.GET.get('refresh') == '1':
        resumo_dia, resumo_mes, _, _, data_fixa = _resumo_lancamentos_por_competencia(ano, mes, dia)
        lancamentos_dia = (
            LancamentoSalao.objects.filter(data=data_fixa)
            .select_related('servico', 'forma_pagamento')
            .order_by('-id')[:30]
        )
        rows_html = render_to_string(
            'salao/partials/lancamentos_dia_rows.html',
            {
                'lancamentos_dia': lancamentos_dia,
                'ano': ano,
                'mes': mes,
                'dia': dia,
            },
            request=request,
        )
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
                'rows_html': rows_html,
            }
        )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_lancamento':
            codigo = _normalize_codigo(request.POST.get('codigo'))
            codigo_forma = _normalize_codigo(request.POST.get('codigo_forma_pagamento'))
            valor_bruto = _parse_decimal(request.POST.get('valor_bruto'))
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

            if not codigo_forma:
                messages.error(request, 'Informe o código da forma de pagamento.')
                return _redirect_lancamentos(ano, mes, dia_post)

            forma_pagamento = FormaPagamentoSalao.objects.filter(codigo=codigo_forma, ativo=True).first()
            if not forma_pagamento:
                messages.error(request, f"Código de pagamento '{codigo_forma}' não encontrado.")
                return _redirect_lancamentos(ano, mes, dia_post)

            parcelas = _parse_parcelas(request.POST.get('parcelas'), default=1)
            if not forma_pagamento.aceita_parcelamento:
                parcelas = 1

            taxa = TaxaFormaPagamentoSalao.objects.filter(
                forma_pagamento=forma_pagamento,
                parcelas=parcelas,
            ).first()
            if not taxa:
                messages.error(request, 'Taxa não cadastrada para essa forma de pagamento e parcela.')
                return _redirect_lancamentos(ano, mes, dia_post)

            if valor_bruto is None or valor_bruto < Decimal('0.00'):
                messages.error(request, 'Informe um valor bruto válido.')
                return _redirect_lancamentos(ano, mes, dia_post)

            valor_taxa, valor_liquido = _calcular_liquido_com_taxa(valor_bruto, taxa.percentual)

            LancamentoSalao.objects.create(
                data=date(ano, mes, dia_post),
                servico=servico,
                forma_pagamento=forma_pagamento,
                parcelas=parcelas,
                valor_bruto=valor_bruto,
                taxa_percentual_aplicada=taxa.percentual,
                valor_taxa=valor_taxa,
                valor_cobrado=valor_liquido,
            )
            messages.success(request, f'Lançamento salvo. Líquido: R$ {valor_liquido}.')
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

            forma_pagamento_id = request.POST.get('forma_pagamento_id')
            forma_pagamento = FormaPagamentoSalao.objects.filter(id=forma_pagamento_id, ativo=True).first()
            if not forma_pagamento:
                messages.error(request, 'Selecione uma forma de pagamento ativa válida.')
                return _redirect_lancamentos(ano, mes, dia)

            parcelas = _parse_parcelas(request.POST.get('parcelas'), default=1)
            if not forma_pagamento.aceita_parcelamento:
                parcelas = 1

            taxa = TaxaFormaPagamentoSalao.objects.filter(
                forma_pagamento=forma_pagamento,
                parcelas=parcelas,
            ).first()
            if not taxa:
                messages.error(request, 'Taxa não cadastrada para essa forma de pagamento e parcela.')
                return _redirect_lancamentos(ano, mes, dia)

            valor_bruto = _parse_decimal(request.POST.get('valor_bruto'))
            if valor_bruto is None or valor_bruto < Decimal('0.00'):
                messages.error(request, 'Informe um valor bruto válido para edição.')
                return _redirect_lancamentos(ano, mes, dia)

            valor_taxa, valor_liquido = _calcular_liquido_com_taxa(valor_bruto, taxa.percentual)

            lancamento.data = data_editada
            lancamento.servico = servico
            lancamento.forma_pagamento = forma_pagamento
            lancamento.parcelas = parcelas
            lancamento.valor_bruto = valor_bruto
            lancamento.taxa_percentual_aplicada = taxa.percentual
            lancamento.valor_taxa = valor_taxa
            lancamento.valor_cobrado = valor_liquido
            lancamento.save(
                update_fields=[
                    'data',
                    'servico',
                    'forma_pagamento',
                    'parcelas',
                    'valor_bruto',
                    'taxa_percentual_aplicada',
                    'valor_taxa',
                    'valor_cobrado',
                    'atualizado_em',
                ]
            )
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
        .select_related('servico', 'forma_pagamento')
        .order_by('-id')[:30]
    )

    edit_lancamento = None
    edit_lancamento_id = request.GET.get('edit')
    if edit_lancamento_id:
        edit_lancamento = LancamentoSalao.objects.filter(id=edit_lancamento_id).select_related(
            'servico', 'forma_pagamento'
        ).first()

    context = {
        'active_tab': 'lancamentos',
        'ano': ano,
        'mes': mes,
        'dia': dia,
        'month_options': MONTH_OPTIONS,
        'year_options': _build_year_options(),
        'servicos_ativos': servicos_ativos,
        'formas_pagamento_ativas': formas_pagamento_ativas,
        'servicos_catalogo': [
            {
                'id': servico.id,
                'codigo': servico.codigo,
                'nome': servico.nome,
                'valor_padrao': str(servico.valor_padrao),
            }
            for servico in servicos_ativos
        ],
        'formas_catalogo': _build_formas_catalogo(formas_pagamento_ativas),
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
        CategoriaDespesaSalao.objects.filter(ativo=True).order_by('nome')
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
            parcelas = _parse_parcelas(request.POST.get('parcelas'), default=1)

            grupo_parcelamento_id = uuid.uuid4() if parcelas > 1 else None
            valores_parcelados = _split_amount_evenly(valor, parcelas)
            despesas_para_criar = []

            for idx in range(parcelas):
                data_parcela = _add_months_preserving_day(data_despesa, idx)
                despesas_para_criar.append(
                    DespesaSalao(
                        data=data_parcela,
                        categoria=categoria,
                        valor=valores_parcelados[idx],
                        observacao=observacao,
                        grupo_parcelamento_id=grupo_parcelamento_id,
                        parcela_numero=idx + 1,
                        parcelas_total=parcelas,
                    )
                )

            DespesaSalao.objects.bulk_create(despesas_para_criar)
            if parcelas > 1:
                messages.success(request, f'Despesa parcelada salva em {parcelas}x.')
            else:
                messages.success(request, 'Despesa salva com sucesso.')
            return _redirect_despesas(ano, mes)

        if action == 'delete_despesa':
            despesa_id = request.POST.get('despesa_id')
            despesa = get_object_or_404(DespesaSalao, id=despesa_id)
            despesa.delete()
            messages.success(request, 'Despesa removida com sucesso.')
            return _redirect_despesas(ano, mes)

        if action == 'delete_despesa_grupo':
            grupo_id = request.POST.get('grupo_parcelamento_id')
            try:
                grupo_uuid = uuid.UUID(str(grupo_id))
            except (TypeError, ValueError):
                messages.error(request, 'Grupo de parcelamento inválido.')
                return _redirect_despesas(ano, mes)

            deleted_count, _ = DespesaSalao.objects.filter(grupo_parcelamento_id=grupo_uuid).delete()
            if deleted_count > 0:
                messages.success(request, 'Grupo de despesas parceladas removido com sucesso.')
            else:
                messages.warning(request, 'Nenhuma despesa encontrada para o grupo informado.')
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
        .order_by('data', 'parcela_numero', 'id')[:300]
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
            ativo = _parse_checkbox(request.POST.get('ativo'))

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
            ativo = _parse_checkbox(request.POST.get('ativo'))

            if not codigo or not nome or valor_padrao is None:
                messages.error(request, 'Preencha código, nome e valor padrão válidos.')
                return _redirect_servicos()

            if ServicoSalao.objects.exclude(id=servico.id).filter(codigo=codigo).exists():
                messages.error(request, f'Já existe outro serviço com código {codigo}.')
                return _redirect_servicos()

            servico.codigo = codigo
            servico.nome = nome
            servico.valor_padrao = valor_padrao
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

    servicos_qs = ServicoSalao.objects.all().order_by('codigo')
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
            ativo = _parse_checkbox(request.POST.get('ativo'))

            if not nome:
                messages.error(request, 'Informe o nome da categoria.')
                return _redirect_categorias()

            if CategoriaDespesaSalao.objects.filter(nome__iexact=nome).exists():
                messages.error(request, f'Categoria "{nome}" já existe.')
                return _redirect_categorias()

            CategoriaDespesaSalao.objects.create(
                nome=nome,
                ativo=ativo,
            )
            messages.success(request, 'Categoria criada com sucesso.')
            return _redirect_categorias()

        if action == 'update_categoria':
            categoria_id = request.POST.get('categoria_id')
            categoria = get_object_or_404(CategoriaDespesaSalao, id=categoria_id)

            nome = (request.POST.get('nome') or '').strip()
            ativo = _parse_checkbox(request.POST.get('ativo'))

            if not nome:
                messages.error(request, 'Informe o nome da categoria.')
                return _redirect_categorias()

            if CategoriaDespesaSalao.objects.exclude(id=categoria.id).filter(nome__iexact=nome).exists():
                messages.error(request, f'Categoria "{nome}" já existe.')
                return _redirect_categorias()

            categoria.nome = nome
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

    categorias_qs = CategoriaDespesaSalao.objects.all().order_by('nome')
    edit_id = request.GET.get('edit')
    edit_categoria = CategoriaDespesaSalao.objects.filter(id=edit_id).first() if edit_id else None

    context = {
        'active_tab': 'categorias',
        'categorias': categorias_qs,
        'edit_categoria': edit_categoria,
    }
    return render(request, 'salao/categorias.html', context)


@_salao_superuser_required
def pagamentos(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_forma_pagamento':
            codigo = _normalize_codigo(request.POST.get('codigo'))
            nome = (request.POST.get('nome') or '').strip()
            aceita_parcelamento = _parse_checkbox(request.POST.get('aceita_parcelamento'))
            ativo = _parse_checkbox(request.POST.get('ativo'))

            if not codigo or not nome:
                messages.error(request, 'Informe código e nome da forma de pagamento.')
                return _redirect_pagamentos()

            if FormaPagamentoSalao.objects.filter(codigo=codigo).exists():
                messages.error(request, f'Já existe forma de pagamento com código {codigo}.')
                return _redirect_pagamentos()

            FormaPagamentoSalao.objects.create(
                codigo=codigo,
                nome=nome,
                aceita_parcelamento=aceita_parcelamento,
                ativo=ativo,
            )
            messages.success(request, 'Forma de pagamento criada com sucesso.')
            return _redirect_pagamentos()

        if action == 'update_forma_pagamento':
            forma_id = request.POST.get('forma_id')
            forma = get_object_or_404(FormaPagamentoSalao, id=forma_id)

            codigo = _normalize_codigo(request.POST.get('codigo'))
            nome = (request.POST.get('nome') or '').strip()
            aceita_parcelamento = _parse_checkbox(request.POST.get('aceita_parcelamento'))
            ativo = _parse_checkbox(request.POST.get('ativo'))

            if not codigo or not nome:
                messages.error(request, 'Informe código e nome da forma de pagamento.')
                return _redirect_pagamentos()

            if FormaPagamentoSalao.objects.exclude(id=forma.id).filter(codigo=codigo).exists():
                messages.error(request, f'Já existe outra forma de pagamento com código {codigo}.')
                return _redirect_pagamentos()

            forma.codigo = codigo
            forma.nome = nome
            forma.aceita_parcelamento = aceita_parcelamento
            forma.ativo = ativo
            forma.save()
            messages.success(request, 'Forma de pagamento atualizada com sucesso.')
            return _redirect_pagamentos(forma_taxa_id=forma.id)

        if action == 'delete_forma_pagamento':
            forma_id = request.POST.get('forma_id')
            forma = get_object_or_404(FormaPagamentoSalao, id=forma_id)
            try:
                forma.delete()
                messages.success(request, 'Forma de pagamento removida com sucesso.')
            except ProtectedError:
                messages.error(
                    request,
                    'Não foi possível remover: existem lançamentos vinculados a essa forma de pagamento.',
                )
            return _redirect_pagamentos()

        if action == 'save_taxas_forma':
            forma_id = request.POST.get('forma_id')
            forma = get_object_or_404(FormaPagamentoSalao, id=forma_id)

            parcelas_range = range(1, 13) if forma.aceita_parcelamento else range(1, 2)
            taxas_to_upsert = []
            parcelas_to_keep = set()

            for parcela in parcelas_range:
                raw_percentual = (request.POST.get(f'taxa_{parcela}') or '').strip()
                if raw_percentual == '':
                    continue
                percentual = _parse_decimal(raw_percentual)
                if percentual is None or percentual < Decimal('0.00') or percentual > Decimal('100.00'):
                    messages.error(request, f'Taxa inválida para {parcela}x.')
                    return _redirect_pagamentos(forma_taxa_id=forma.id)
                parcelas_to_keep.add(parcela)
                taxas_to_upsert.append((parcela, percentual))

            with transaction.atomic():
                for parcela, percentual in taxas_to_upsert:
                    TaxaFormaPagamentoSalao.objects.update_or_create(
                        forma_pagamento=forma,
                        parcelas=parcela,
                        defaults={'percentual': percentual},
                    )
                TaxaFormaPagamentoSalao.objects.filter(forma_pagamento=forma).exclude(
                    parcelas__in=parcelas_to_keep
                ).delete()

            messages.success(request, 'Taxas salvas com sucesso.')
            return _redirect_pagamentos(forma_taxa_id=forma.id)

    formas_qs = list(FormaPagamentoSalao.objects.all().order_by('codigo'))
    edit_forma = None
    edit_forma_id = request.GET.get('edit_forma')
    if edit_forma_id:
        edit_forma = FormaPagamentoSalao.objects.filter(id=edit_forma_id).first()

    forma_taxa = None
    forma_taxa_id = request.GET.get('forma_taxa')
    if forma_taxa_id:
        forma_taxa = FormaPagamentoSalao.objects.filter(id=forma_taxa_id).first()
    if not forma_taxa and formas_qs:
        forma_taxa = formas_qs[0]

    taxas_map = {}
    parcelas_range = range(1, 2)
    if forma_taxa:
        parcelas_range = range(1, 13) if forma_taxa.aceita_parcelamento else range(1, 2)
        taxas_map = {
            taxa.parcelas: taxa.percentual
            for taxa in TaxaFormaPagamentoSalao.objects.filter(forma_pagamento=forma_taxa)
        }
    taxas_rows = [
        {
            'parcela': parcela,
            'percentual': taxas_map.get(parcela),
        }
        for parcela in parcelas_range
    ]

    context = {
        'active_tab': 'pagamentos',
        'formas_pagamento': formas_qs,
        'edit_forma': edit_forma,
        'forma_taxa': forma_taxa,
        'taxas_rows': taxas_rows,
    }
    return render(request, 'salao/pagamentos.html', context)


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

    faturamento_liquido = lancamentos_mes.aggregate(total=Sum('valor_cobrado'))['total'] or Decimal('0.00')
    faturamento_bruto_cliente = lancamentos_mes.aggregate(total=Sum('valor_bruto'))['total'] or Decimal('0.00')
    taxas_total = lancamentos_mes.aggregate(total=Sum('valor_taxa'))['total'] or Decimal('0.00')
    despesas_total = despesas_mes.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    atendimentos_total = lancamentos_mes.count()
    ticket_medio = (
        (faturamento_liquido / Decimal(atendimentos_total)).quantize(Decimal('0.01'))
        if atendimentos_total > 0
        else Decimal('0.00')
    )

    comissao_calculada = (
        (faturamento_liquido * comissao.percentual) / Decimal('100.00')
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    comissao_paga = comissao_calculada
    valor_pos_comissao = faturamento_liquido - comissao_paga
    lucro = valor_pos_comissao - despesas_total
    impacto_taxas_percentual = (
        (taxas_total / faturamento_bruto_cliente) * Decimal('100.00')
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if faturamento_bruto_cliente > Decimal('0.00') else Decimal('0.00')

    meta_faturamento = comissao.meta_faturamento
    percentual_meta_atingido = None
    valor_faltante_meta = None
    if meta_faturamento and meta_faturamento > Decimal('0.00'):
        percentual_meta_atingido = (
            (faturamento_liquido / meta_faturamento) * Decimal('100.00')
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        valor_faltante_meta = max(
            (meta_faturamento - faturamento_liquido).quantize(
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
    chart_taxas = []
    chart_despesas = []
    chart_lucro = []
    chart_atendimentos = []
    chart_ticket = []

    for ano_item, mes_item in serie_meses:
        label = f"{mes_item:02d}/{ano_item}"
        lancamentos_item = LancamentoSalao.objects.filter(data__year=ano_item, data__month=mes_item)
        despesas_item = DespesaSalao.objects.filter(data__year=ano_item, data__month=mes_item)

        faturamento_item = lancamentos_item.aggregate(total=Sum('valor_cobrado'))['total'] or Decimal('0.00')
        taxas_item = lancamentos_item.aggregate(total=Sum('valor_taxa'))['total'] or Decimal('0.00')
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
        chart_taxas.append(float(taxas_item))
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
        'faturamento_bruto': faturamento_liquido,
        'faturamento_bruto_cliente': faturamento_bruto_cliente,
        'taxas_total': taxas_total,
        'impacto_taxas_percentual': impacto_taxas_percentual,
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
        'meta_gauge_chart': {
            'tem_meta': bool(meta_faturamento and meta_faturamento > Decimal('0.00')),
            'meta': float(meta_faturamento or Decimal('0.00')),
            'realizado': float(faturamento_liquido),
            'percentual_real': float(percentual_meta_atingido or Decimal('0.00')),
            'percentual_gauge': float(min(percentual_meta_atingido or Decimal('0.00'), Decimal('100.00'))),
        },
        'comparativo_chart': {
            'labels': chart_labels,
            'faturamento': chart_faturamento,
            'taxas': chart_taxas,
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
