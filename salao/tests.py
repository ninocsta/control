from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.test import TestCase
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


class SalaoViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='test1234',
        )

        self.servico = ServicoSalao.objects.create(
            codigo='C01',
            nome='Corte Feminino',
            valor_padrao=Decimal('80.00'),
            ativo=True,
        )
        self.categoria = CategoriaDespesaSalao.objects.create(
            nome='Produtos',
            ativo=True,
        )

        self.forma_nao_informado, _ = FormaPagamentoSalao.objects.get_or_create(
            codigo='0',
            defaults={
                'nome': 'Não informado',
                'ativo': True,
                'aceita_parcelamento': False,
            },
        )
        self.forma_pix, _ = FormaPagamentoSalao.objects.get_or_create(
            codigo='1',
            defaults={
                'nome': 'PIX',
                'ativo': True,
                'aceita_parcelamento': False,
            },
        )
        self.forma_credito, _ = FormaPagamentoSalao.objects.get_or_create(
            codigo='2',
            defaults={
                'nome': 'Crédito',
                'ativo': True,
                'aceita_parcelamento': True,
            },
        )
        self.forma_dinheiro, _ = FormaPagamentoSalao.objects.get_or_create(
            codigo='3',
            defaults={
                'nome': 'Dinheiro',
                'ativo': True,
                'aceita_parcelamento': False,
            },
        )
        self.forma_debito, _ = FormaPagamentoSalao.objects.get_or_create(
            codigo='4',
            defaults={
                'nome': 'Débito',
                'ativo': True,
                'aceita_parcelamento': False,
            },
        )

        TaxaFormaPagamentoSalao.objects.update_or_create(
            forma_pagamento=self.forma_nao_informado,
            parcelas=1,
            defaults={'percentual': Decimal('0.00')},
        )
        TaxaFormaPagamentoSalao.objects.update_or_create(
            forma_pagamento=self.forma_pix,
            parcelas=1,
            defaults={'percentual': Decimal('0.00')},
        )
        TaxaFormaPagamentoSalao.objects.update_or_create(
            forma_pagamento=self.forma_dinheiro,
            parcelas=1,
            defaults={'percentual': Decimal('0.00')},
        )
        TaxaFormaPagamentoSalao.objects.update_or_create(
            forma_pagamento=self.forma_debito,
            parcelas=1,
            defaults={'percentual': Decimal('3.00')},
        )
        TaxaFormaPagamentoSalao.objects.update_or_create(
            forma_pagamento=self.forma_credito,
            parcelas=1,
            defaults={'percentual': Decimal('4.00')},
        )
        TaxaFormaPagamentoSalao.objects.update_or_create(
            forma_pagamento=self.forma_credito,
            parcelas=2,
            defaults={'percentual': Decimal('5.00')},
        )

    def _login(self):
        self.client.force_login(self.superuser)

    def _create_lancamento(
        self,
        *,
        data,
        valor_bruto,
        forma_pagamento=None,
        parcelas=1,
        taxa_percentual=Decimal('0.00'),
    ):
        forma = forma_pagamento or self.forma_dinheiro
        valor_taxa = (valor_bruto * taxa_percentual / Decimal('100.00')).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP,
        )
        valor_liquido = (valor_bruto - valor_taxa).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return LancamentoSalao.objects.create(
            data=data,
            servico=self.servico,
            forma_pagamento=forma,
            parcelas=parcelas,
            valor_bruto=valor_bruto,
            taxa_percentual_aplicada=taxa_percentual,
            valor_taxa=valor_taxa,
            valor_cobrado=valor_liquido,
        )

    def test_dashboard_auto_create_comissao(self):
        self._login()
        self.assertEqual(ComissaoMensalSalao.objects.count(), 0)

        response = self.client.get(reverse('salao:dashboard'), {'ano': 2026, 'mes': 2})

        self.assertEqual(response.status_code, 200)
        comissao = ComissaoMensalSalao.objects.get(ano=2026, mes=2)
        self.assertEqual(comissao.percentual, Decimal('20.00'))

    def test_dashboard_calculo_sem_override(self):
        self._login()

        self._create_lancamento(
            data=date(2026, 3, 10),
            valor_bruto=Decimal('200.00'),
            forma_pagamento=self.forma_dinheiro,
            taxa_percentual=Decimal('0.00'),
        )
        self._create_lancamento(
            data=date(2026, 3, 12),
            valor_bruto=Decimal('100.00'),
            forma_pagamento=self.forma_dinheiro,
            taxa_percentual=Decimal('0.00'),
        )
        DespesaSalao.objects.create(
            data=date(2026, 3, 13),
            categoria=self.categoria,
            valor=Decimal('50.00'),
            observacao='Compra mensal',
        )

        response = self.client.get(reverse('salao:dashboard'), {'ano': 2026, 'mes': 3})
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['faturamento_bruto'], Decimal('300.00'))
        self.assertEqual(response.context['taxas_total'], Decimal('0.00'))
        self.assertEqual(response.context['comissao_calculada'], Decimal('60.00'))
        self.assertEqual(response.context['despesas_total'], Decimal('50.00'))
        self.assertEqual(response.context['lucro'], Decimal('190.00'))
        self.assertIn('meta_gauge_chart', response.context)

    def test_dashboard_ignora_override_e_usa_comissao_automatica(self):
        self._login()

        self._create_lancamento(
            data=date(2026, 3, 10),
            valor_bruto=Decimal('300.00'),
            forma_pagamento=self.forma_dinheiro,
            taxa_percentual=Decimal('0.00'),
        )
        ComissaoMensalSalao.objects.update_or_create(
            ano=2026,
            mes=3,
            defaults={
                'percentual': Decimal('20.00'),
                'valor_pago_override': Decimal('40.00'),
            },
        )

        response = self.client.get(reverse('salao:dashboard'), {'ano': 2026, 'mes': 3})
        self.assertEqual(response.context['comissao_calculada'], Decimal('60.00'))
        self.assertEqual(response.context['lucro'], Decimal('240.00'))

    def test_dashboard_salva_meta_e_calcula_percentual_atingido(self):
        self._login()

        self._create_lancamento(
            data=date(2026, 3, 10),
            valor_bruto=Decimal('500.00'),
            forma_pagamento=self.forma_dinheiro,
            taxa_percentual=Decimal('0.00'),
        )

        post_response = self.client.post(
            reverse('salao:dashboard'),
            {
                'action': 'update_meta',
                'ano': 2026,
                'mes': 3,
                'meta_faturamento': '1000,00',
            },
        )
        self.assertEqual(post_response.status_code, 302)

        response = self.client.get(reverse('salao:dashboard'), {'ano': 2026, 'mes': 3})
        self.assertEqual(response.context['meta_faturamento'], Decimal('1000.00'))
        self.assertEqual(response.context['percentual_meta_atingido'], Decimal('50.00'))

    def test_lancamento_codigo_invalido_bloqueia_save(self):
        self._login()

        response = self.client.post(
            reverse('salao:lancamentos'),
            {
                'action': 'create_lancamento',
                'ano': 2026,
                'mes': 3,
                'dia': 10,
                'codigo': 'X99',
                'codigo_forma_pagamento': '3',
                'parcelas': 1,
                'valor_bruto': '70,00',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(LancamentoSalao.objects.count(), 0)

    def test_lancamento_forma_invalida_bloqueia_save(self):
        self._login()

        response = self.client.post(
            reverse('salao:lancamentos'),
            {
                'action': 'create_lancamento',
                'ano': 2026,
                'mes': 3,
                'dia': 10,
                'codigo': 'C01',
                'codigo_forma_pagamento': '999',
                'parcelas': 1,
                'valor_bruto': '70,00',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(LancamentoSalao.objects.count(), 0)

    def test_lancamento_taxa_ausente_bloqueia_save(self):
        self._login()

        response = self.client.post(
            reverse('salao:lancamentos'),
            {
                'action': 'create_lancamento',
                'ano': 2026,
                'mes': 3,
                'dia': 10,
                'codigo': 'C01',
                'codigo_forma_pagamento': '2',
                'parcelas': 12,
                'valor_bruto': '100,00',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(LancamentoSalao.objects.count(), 0)

    def test_lancamento_codigo_valido_salva_com_taxa(self):
        self._login()

        response = self.client.post(
            reverse('salao:lancamentos'),
            {
                'action': 'create_lancamento',
                'ano': 2026,
                'mes': 3,
                'dia': 10,
                'codigo': 'c01',
                'codigo_forma_pagamento': '4',
                'parcelas': 1,
                'valor_bruto': '100,00',
            },
        )

        self.assertEqual(response.status_code, 302)
        lanc = LancamentoSalao.objects.get()
        self.assertEqual(lanc.valor_bruto, Decimal('100.00'))
        self.assertEqual(lanc.valor_taxa, Decimal('3.00'))
        self.assertEqual(lanc.valor_cobrado, Decimal('97.00'))

    def test_endpoint_refresh_lancamentos_por_dia_retorna_rows_html(self):
        self._login()

        self._create_lancamento(
            data=date(2026, 3, 10),
            valor_bruto=Decimal('80.00'),
            forma_pagamento=self.forma_dinheiro,
            taxa_percentual=Decimal('0.00'),
        )

        response = self.client.get(
            reverse('salao:lancamentos'),
            {
                'ano': 2026,
                'mes': 3,
                'dia': 10,
                'refresh': 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('rows_html', payload)
        self.assertIn('Corte Feminino', payload['rows_html'])

    def test_editar_e_excluir_lancamento(self):
        self._login()

        lancamento = self._create_lancamento(
            data=date(2026, 3, 10),
            valor_bruto=Decimal('80.00'),
            forma_pagamento=self.forma_dinheiro,
            taxa_percentual=Decimal('0.00'),
        )

        edit_response = self.client.post(
            reverse('salao:lancamentos'),
            {
                'action': 'update_lancamento',
                'lancamento_id': lancamento.id,
                'ano': 2026,
                'mes': 3,
                'dia': 10,
                'data': '2026-03-11',
                'servico_id': self.servico.id,
                'forma_pagamento_id': self.forma_debito.id,
                'parcelas': 1,
                'valor_bruto': '95,00',
            },
        )
        self.assertEqual(edit_response.status_code, 302)

        lancamento.refresh_from_db()
        self.assertEqual(lancamento.data, date(2026, 3, 11))
        self.assertEqual(lancamento.valor_bruto, Decimal('95.00'))
        self.assertEqual(lancamento.valor_taxa, Decimal('2.85'))
        self.assertEqual(lancamento.valor_cobrado, Decimal('92.15'))

        delete_response = self.client.post(
            reverse('salao:lancamentos'),
            {
                'action': 'delete_lancamento',
                'lancamento_id': lancamento.id,
                'ano': 2026,
                'mes': 3,
                'dia': 10,
            },
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertEqual(LancamentoSalao.objects.count(), 0)

    def test_criar_despesa_parcelada_em_4x(self):
        self._login()

        response = self.client.post(
            reverse('salao:despesas'),
            {
                'action': 'create_despesa',
                'ano': 2026,
                'mes': 3,
                'data': '2026-03-31',
                'categoria_id': self.categoria.id,
                'valor': '2000,00',
                'parcelas': 4,
                'observacao': 'Cadeira nova',
            },
        )
        self.assertEqual(response.status_code, 302)

        despesas = list(DespesaSalao.objects.order_by('data', 'parcela_numero'))
        self.assertEqual(len(despesas), 4)
        self.assertEqual([d.parcela_numero for d in despesas], [1, 2, 3, 4])
        self.assertEqual([d.parcelas_total for d in despesas], [4, 4, 4, 4])
        self.assertEqual(despesas[0].data, date(2026, 3, 31))
        self.assertEqual(despesas[1].data, date(2026, 4, 30))
        self.assertEqual(despesas[2].data, date(2026, 5, 31))
        self.assertEqual(despesas[3].data, date(2026, 6, 30))
        self.assertEqual(sum(d.valor for d in despesas), Decimal('2000.00'))
        self.assertIsNotNone(despesas[0].grupo_parcelamento_id)

    def test_excluir_grupo_despesa_parcelada(self):
        self._login()

        self.client.post(
            reverse('salao:despesas'),
            {
                'action': 'create_despesa',
                'ano': 2026,
                'mes': 3,
                'data': '2026-03-10',
                'categoria_id': self.categoria.id,
                'valor': '300,00',
                'parcelas': 3,
                'observacao': 'Teste',
            },
        )
        first = DespesaSalao.objects.first()
        self.assertIsNotNone(first.grupo_parcelamento_id)

        response = self.client.post(
            reverse('salao:despesas'),
            {
                'action': 'delete_despesa_grupo',
                'grupo_parcelamento_id': str(first.grupo_parcelamento_id),
                'ano': 2026,
                'mes': 3,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DespesaSalao.objects.count(), 0)

    def test_criar_editar_excluir_despesa(self):
        self._login()

        create_response = self.client.post(
            reverse('salao:despesas'),
            {
                'action': 'create_despesa',
                'ano': 2026,
                'mes': 3,
                'data': '2026-03-14',
                'categoria_id': self.categoria.id,
                'valor': '45,00',
                'parcelas': 1,
                'observacao': 'Luva descartável',
            },
        )
        self.assertEqual(create_response.status_code, 302)
        self.assertEqual(DespesaSalao.objects.count(), 1)

        despesa = DespesaSalao.objects.first()

        edit_response = self.client.post(
            reverse('salao:despesas'),
            {
                'action': 'update_despesa',
                'despesa_id': despesa.id,
                'ano': 2026,
                'mes': 3,
                'data': '2026-03-15',
                'categoria_id': self.categoria.id,
                'valor': '55,00',
                'observacao': 'Produto extra',
            },
        )
        self.assertEqual(edit_response.status_code, 302)

        despesa.refresh_from_db()
        self.assertEqual(despesa.data, date(2026, 3, 15))
        self.assertEqual(despesa.valor, Decimal('55.00'))

        delete_response = self.client.post(
            reverse('salao:despesas'),
            {
                'action': 'delete_despesa',
                'despesa_id': despesa.id,
                'ano': 2026,
                'mes': 3,
            },
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertEqual(DespesaSalao.objects.count(), 0)

    def test_crud_servicos_pela_tela(self):
        self._login()

        create_response = self.client.post(
            reverse('salao:servicos'),
            {
                'action': 'create_servico',
                'codigo': 'P10',
                'nome': 'Progressiva',
                'valor_padrao': '250,00',
                'ativo': 'on',
            },
        )
        self.assertEqual(create_response.status_code, 302)
        created = ServicoSalao.objects.get(codigo='P10')
        self.assertEqual(created.valor_padrao, Decimal('250.00'))

        update_response = self.client.post(
            reverse('salao:servicos'),
            {
                'action': 'update_servico',
                'servico_id': created.id,
                'codigo': 'P10',
                'nome': 'Progressiva Premium',
                'valor_padrao': '300,00',
            },
        )
        self.assertEqual(update_response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.nome, 'Progressiva Premium')
        self.assertEqual(created.valor_padrao, Decimal('300.00'))
        self.assertFalse(created.ativo)

    def test_crud_categorias_pela_tela(self):
        self._login()

        create_response = self.client.post(
            reverse('salao:categorias'),
            {
                'action': 'create_categoria',
                'nome': 'Lavanderia',
                'ativo': 'on',
            },
        )
        self.assertEqual(create_response.status_code, 302)
        created = CategoriaDespesaSalao.objects.get(nome='Lavanderia')
        self.assertTrue(created.ativo)

        update_response = self.client.post(
            reverse('salao:categorias'),
            {
                'action': 'update_categoria',
                'categoria_id': created.id,
                'nome': 'Lavanderia e Toalhas',
            },
        )
        self.assertEqual(update_response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.nome, 'Lavanderia e Toalhas')
        self.assertFalse(created.ativo)

    def test_crud_pagamentos_e_taxas(self):
        self._login()

        create_response = self.client.post(
            reverse('salao:pagamentos'),
            {
                'action': 'create_forma_pagamento',
                'codigo': '9',
                'nome': 'Carteira Digital',
                'aceita_parcelamento': 'on',
                'ativo': 'on',
            },
        )
        self.assertEqual(create_response.status_code, 302)
        forma = FormaPagamentoSalao.objects.get(codigo='9')

        save_taxas_response = self.client.post(
            reverse('salao:pagamentos'),
            {
                'action': 'save_taxas_forma',
                'forma_id': forma.id,
                'taxa_1': '1,5',
                'taxa_2': '2,5',
            },
        )
        self.assertEqual(save_taxas_response.status_code, 302)
        self.assertTrue(TaxaFormaPagamentoSalao.objects.filter(forma_pagamento=forma, parcelas=1).exists())
        self.assertTrue(TaxaFormaPagamentoSalao.objects.filter(forma_pagamento=forma, parcelas=2).exists())
