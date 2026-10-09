from datetime import date

from django import forms
from django.utils import timezone

from clientes.models import Cliente
from contratos.models import Contrato, ContratoReajuste
from infra.financeiro.models import DespesaAdicional
from infra.recursos.models import CustoRecurso, Recurso, RecursoContrato


class Estilo:
    """Classe .input em todo campo e <input type=date> nos campos de data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(field, forms.DateField):
                w.input_type = 'date'
                w.format = '%Y-%m-%d'
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault('class', 'check')
            else:
                w.attrs.setdefault('class', 'input')
            if isinstance(w, forms.Textarea):
                w.attrs.setdefault('rows', 3)


class ClienteForm(Estilo, forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ('nome', 'tipo', 'telefone', 'email', 'vencimento_padrao', 'descricao_cobranca', 'ativo')
        labels = {'vencimento_padrao': 'Dia de vencimento', 'descricao_cobranca': 'Descrição na cobrança'}
        help_texts = {
            'telefone': 'Com DDD, só números (ex: 51999998888). É para onde vão os lembretes no WhatsApp.',
            'vencimento_padrao': 'Lembretes saem 5 e 2 dias antes e no dia.',
        }


class ContratoForm(Estilo, forms.ModelForm):
    class Meta:
        model = Contrato
        fields = ('cliente', 'nome', 'valor_mensal', 'data_inicio', 'data_fim', 'descricao', 'arquivo_contrato')
        labels = {'data_fim': 'Data de fim', 'arquivo_contrato': 'Arquivo do contrato'}
        help_texts = {
            'data_inicio': 'Começando no dia 1, já cobra nesse mês; depois do dia 1, cobra a partir do mês seguinte.',
            'valor_mensal': 'Valor inicial. Mudança futura de valor: use reajuste.',
        }


class ReajusteForm(Estilo, forms.ModelForm):
    class Meta:
        model = ContratoReajuste
        fields = ('vigente_desde', 'valor_mensal', 'observacao')
        labels = {'vigente_desde': 'A partir de', 'valor_mensal': 'Novo valor mensal', 'observacao': 'Observação'}
        help_texts = {'vigente_desde': 'Vale a partir do mês desta data.'}


class EncerrarForm(Estilo, forms.Form):
    data_fim = forms.DateField(label='Último dia', initial=timezone.localdate)


class AvulsaForm(Estilo, forms.Form):
    contrato = forms.ModelChoiceField(
        Contrato.objects.select_related('cliente').order_by('cliente__nome', '-data_inicio'),
        help_text='A receita entra na margem deste contrato.',
    )
    descricao = forms.CharField(max_length=255, label='Descrição', help_text='Ex: horas extras setembro')
    valor = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    vencimento = forms.DateField()

    def __init__(self, *args, cliente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contrato'].label_from_instance = lambda c: f'{c.cliente.nome} · {c.nome}'
        if cliente:
            self.fields['contrato'].queryset = self.fields['contrato'].queryset.filter(cliente=cliente)


class FaturaForm(Estilo, forms.Form):
    descricao = forms.CharField(max_length=255, required=False, label='Descrição')
    vencimento = forms.DateField()


class PagamentoForm(Estilo, forms.Form):
    pago_em = forms.DateField(label='Pago em', initial=timezone.localdate)


class RecursoForm(Estilo, forms.ModelForm):
    class Meta:
        model = Recurso
        fields = ('tipo', 'nome', 'fornecedor', 'detalhe', 'pai', 'ativo', 'observacoes')
        labels = {'pai': 'Pertence a', 'observacoes': 'Observações'}


class CustoForm(Estilo, forms.ModelForm):
    class Meta:
        model = CustoRecurso
        fields = ('valor_total', 'periodo_meses', 'vencimento', 'pago_pelo_cliente', 'data_inicio', 'data_fim')
        labels = {
            'valor_total': 'Valor pago', 'periodo_meses': 'A cada (meses)', 'vencimento': 'Próxima renovação',
            'pago_pelo_cliente': 'Cliente paga direto ao fornecedor', 'data_inicio': 'Vale desde', 'data_fim': 'Até',
        }
        help_texts = {
            'valor_total': 'Valor de cada renovação (anual de R$ 120 = 120, a cada 12 meses).',
            'pago_pelo_cliente': 'Só controla o vencimento; não entra em custo nem margem.',
            'data_fim': 'Deixe vazio enquanto estiver em uso.',
        }


class VinculoForm(Estilo, forms.ModelForm):
    class Meta:
        model = RecursoContrato
        fields = ('contrato', 'data_inicio')
        labels = {'data_inicio': 'Desde'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contrato'].queryset = Contrato.objects.select_related('cliente').filter(
            data_fim__isnull=True).order_by('cliente__nome')
        self.fields['contrato'].label_from_instance = lambda c: f'{c.cliente.nome} · {c.nome}'
        self.fields['data_inicio'].initial = timezone.localdate


class DespesaForm(Estilo, forms.ModelForm):
    class Meta:
        model = DespesaAdicional
        fields = ('contrato', 'descricao', 'valor', 'observacoes')
        labels = {'descricao': 'Descrição', 'observacoes': 'Observações'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contrato'].queryset = Contrato.objects.select_related('cliente').order_by('cliente__nome')
        self.fields['contrato'].label_from_instance = lambda c: f'{c.cliente.nome} · {c.nome}'


def parse_mes(valor, padrao=None):
    """'2026-11' -> (2026, 11); inválido -> padrão (mês atual)."""
    try:
        ano, mes = (int(x) for x in valor.split('-'))
        date(ano, mes, 1)
        return ano, mes
    except (AttributeError, ValueError):
        hoje = padrao or timezone.localdate()
        return hoje.year, hoje.month
