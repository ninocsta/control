from io import BytesIO
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from .models import (
    CompraEstoqueItemSalao,
    CompraEstoqueSalao,
    CategoriaDespesaSalao,
    ComissaoMensalSalao,
    DespesaSalao,
    FormaPagamentoSalao,
    LancamentoSalao,
    MovimentoEstoqueSalao,
    ProdutoSalao,
    ServicoSalao,
    SubcategoriaDespesaSalao,
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
        self.subcategoria = SubcategoriaDespesaSalao.objects.create(
            categoria=self.categoria,
            nome='Auxiliar Maria',
            ativo=True,
        )
        self.produto = ProdutoSalao.objects.create(
            codigo='P01',
            nome='Máscara Capilar',
            unidade='UN',
            valor_venda_padrao=Decimal('35.00'),
            estoque_minimo=Decimal('2.000'),
            saldo_atual=Decimal('0.000'),
            custo_medio_atual=Decimal('0.00'),
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
        self.assertIn('meta_bullet_chart', response.context)

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

    def test_dashboard_relatorio_lancamentos_excel(self):
        self._login()

        self._create_lancamento(
            data=date(2026, 3, 10),
            valor_bruto=Decimal('100.00'),
            forma_pagamento=self.forma_debito,
            taxa_percentual=Decimal('3.00'),
        )
        self._create_lancamento(
            data=date(2026, 3, 11),
            valor_bruto=Decimal('80.00'),
            forma_pagamento=self.forma_dinheiro,
            taxa_percentual=Decimal('0.00'),
        )
        self._create_lancamento(
            data=date(2026, 2, 5),
            valor_bruto=Decimal('500.00'),
            forma_pagamento=self.forma_pix,
            taxa_percentual=Decimal('0.00'),
        )

        response = self.client.get(
            reverse('salao:dashboard_relatorio_lancamentos'),
            {'ano': 2026, 'mes': 3},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('relatorio_lancamentos_2026_03.xlsx', response['Content-Disposition'])

        workbook = load_workbook(filename=BytesIO(response.content))
        sheet = workbook.active

        headers = [sheet.cell(row=1, column=col).value for col in range(1, 9)]
        self.assertEqual(
            headers,
            [
                'Data',
                'Servico',
                'Forma de pagamento',
                'Valor',
                'Valor taxa',
                'Valor liquido',
                'Valor 20%',
                'Valor apos 20%',
            ],
        )

        self.assertEqual(sheet.max_row, 5)

        primeira_linha = [sheet.cell(row=2, column=col).value for col in range(1, 9)]
        self.assertEqual(primeira_linha[0], '10/03/2026')
        self.assertEqual(primeira_linha[2], self.forma_debito.nome)
        self.assertAlmostEqual(primeira_linha[3], 100.00, places=2)
        self.assertAlmostEqual(primeira_linha[4], 3.00, places=2)
        self.assertAlmostEqual(primeira_linha[5], 97.00, places=2)
        self.assertAlmostEqual(primeira_linha[6], 19.40, places=2)
        self.assertAlmostEqual(primeira_linha[7], 77.60, places=2)

        total_linha = [sheet.cell(row=5, column=col).value for col in range(1, 9)]
        self.assertEqual(total_linha[0], 'TOTAL')
        self.assertAlmostEqual(total_linha[3], 180.00, places=2)
        self.assertAlmostEqual(total_linha[4], 3.00, places=2)
        self.assertAlmostEqual(total_linha[5], 177.00, places=2)
        self.assertAlmostEqual(total_linha[6], 35.40, places=2)
        self.assertAlmostEqual(total_linha[7], 141.60, places=2)

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

    def test_crud_subcategorias_pela_tela(self):
        self._login()
        create_response = self.client.post(
            reverse('salao:categorias'),
            {
                'action': 'create_subcategoria',
                'categoria_id': self.categoria.id,
                'nome': 'Auxiliar Joana',
                'ativo': 'on',
            },
        )
        self.assertEqual(create_response.status_code, 302)
        created = SubcategoriaDespesaSalao.objects.get(nome='Auxiliar Joana')
        self.assertTrue(created.ativo)

        update_response = self.client.post(
            reverse('salao:categorias'),
            {
                'action': 'update_subcategoria',
                'subcategoria_id': created.id,
                'categoria_id': self.categoria.id,
                'nome': 'Auxiliar Joana Silva',
            },
        )
        self.assertEqual(update_response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.nome, 'Auxiliar Joana Silva')
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

    def test_despesa_normal_nao_movimenta_estoque(self):
        self._login()

        response = self.client.post(
            reverse('salao:despesas'),
            {
                'action': 'create_despesa',
                'ano': 2026,
                'mes': 3,
                'data': '2026-03-10',
                'categoria_id': self.categoria.id,
                'valor': '120,00',
                'parcelas': 1,
                'observacao': 'Energia elétrica',
            },
        )
        self.assertEqual(response.status_code, 302)
        despesa = DespesaSalao.objects.get()
        self.assertFalse(despesa.gera_estoque)
        self.assertEqual(MovimentoEstoqueSalao.objects.count(), 0)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.saldo_atual, Decimal('0.000'))

    def test_despesa_salva_subcategoria_quando_informada(self):
        self._login()
        response = self.client.post(
            reverse('salao:despesas'),
            {
                'action': 'create_despesa',
                'ano': 2026,
                'mes': 3,
                'data': '2026-03-21',
                'categoria_id': self.categoria.id,
                'subcategoria_id': self.subcategoria.id,
                'valor': '130,00',
                'parcelas': 1,
                'observacao': 'Pagamento auxiliar',
            },
        )
        self.assertEqual(response.status_code, 302)
        despesa = DespesaSalao.objects.get()
        self.assertEqual(despesa.subcategoria_id, self.subcategoria.id)

    def test_despesa_com_estoque_cria_compra_itens_e_movimento(self):
        self._login()

        response = self.client.post(
            reverse('salao:despesas'),
            {
                'action': 'create_despesa',
                'ano': 2026,
                'mes': 3,
                'data': '2026-03-10',
                'categoria_id': self.categoria.id,
                'parcelas': 1,
                'observacao': 'Compra fornecedor RIGOLIM',
                'gera_estoque': 'on',
                'produto_id[]': [str(self.produto.id)],
                'quantidade[]': ['10'],
                'custo_unitario[]': ['20,00'],
            },
        )
        self.assertEqual(response.status_code, 302)

        despesa = DespesaSalao.objects.get()
        self.assertTrue(despesa.gera_estoque)
        self.assertEqual(despesa.valor, Decimal('200.00'))
        self.assertEqual(CompraEstoqueSalao.objects.count(), 1)
        self.assertEqual(CompraEstoqueItemSalao.objects.count(), 1)
        self.assertEqual(MovimentoEstoqueSalao.objects.count(), 1)

        item = CompraEstoqueItemSalao.objects.first()
        self.assertEqual(item.quantidade, Decimal('10.000'))
        self.assertEqual(item.custo_total, Decimal('200.00'))

        mov = MovimentoEstoqueSalao.objects.first()
        self.assertEqual(mov.tipo, MovimentoEstoqueSalao.TIPO_ENTRADA)
        self.assertEqual(mov.motivo, MovimentoEstoqueSalao.MOTIVO_COMPRA)
        self.assertEqual(mov.valor_custo_total, Decimal('200.00'))

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.saldo_atual, Decimal('10.000'))
        self.assertEqual(self.produto.custo_medio_atual, Decimal('20.00'))

    def test_compra_parcelada_gera_entrada_fisica_unica(self):
        self._login()

        response = self.client.post(
            reverse('salao:despesas'),
            {
                'action': 'create_despesa',
                'ano': 2026,
                'mes': 3,
                'data': '2026-03-05',
                'categoria_id': self.categoria.id,
                'parcelas': 4,
                'observacao': 'Compra parcelada',
                'gera_estoque': 'on',
                'produto_id[]': [str(self.produto.id)],
                'quantidade[]': ['8'],
                'custo_unitario[]': ['10,00'],
            },
        )
        self.assertEqual(response.status_code, 302)

        despesas = DespesaSalao.objects.order_by('parcela_numero')
        self.assertEqual(despesas.count(), 4)
        self.assertEqual(sum(d.valor for d in despesas), Decimal('80.00'))
        self.assertTrue(all(d.gera_estoque for d in despesas))
        self.assertEqual(MovimentoEstoqueSalao.objects.filter(motivo=MovimentoEstoqueSalao.MOTIVO_COMPRA).count(), 1)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.saldo_atual, Decimal('8.000'))

    def test_saida_venda_com_taxa_calcula_liquido_e_lucro(self):
        self._login()
        self.produto.saldo_atual = Decimal('5.000')
        self.produto.custo_medio_atual = Decimal('10.00')
        self.produto.save(update_fields=['saldo_atual', 'custo_medio_atual', 'atualizado_em'])

        response = self.client.post(
            reverse('salao:estoque'),
            {
                'action': 'create_saida_estoque',
                'ano': 2026,
                'mes': 3,
                'data': '2026-03-12',
                'produto_id': self.produto.id,
                'tipo_saida': 'VENDA',
                'quantidade': '2',
                'valor_venda_unitario': '30,00',
                'forma_pagamento_id': self.forma_debito.id,
                'parcelas': 1,
            },
        )
        self.assertEqual(response.status_code, 302)

        mov = MovimentoEstoqueSalao.objects.get(motivo=MovimentoEstoqueSalao.MOTIVO_VENDA)
        self.assertEqual(mov.valor_bruto_venda, Decimal('60.00'))
        self.assertEqual(mov.taxa_percentual_aplicada, Decimal('3.00'))
        self.assertEqual(mov.valor_taxa, Decimal('1.80'))
        self.assertEqual(mov.valor_liquido_venda, Decimal('58.20'))
        self.assertEqual(mov.valor_custo_total, Decimal('20.00'))
        self.assertEqual(mov.lucro_produto, Decimal('38.20'))

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.saldo_atual, Decimal('3.000'))

    def test_saida_venda_sem_taxa_cadastrada_aplica_zero(self):
        self._login()
        self.produto.saldo_atual = Decimal('4.000')
        self.produto.custo_medio_atual = Decimal('10.00')
        self.produto.save(update_fields=['saldo_atual', 'custo_medio_atual', 'atualizado_em'])

        response = self.client.post(
            reverse('salao:estoque'),
            {
                'action': 'create_saida_estoque',
                'ano': 2026,
                'mes': 3,
                'data': '2026-03-12',
                'produto_id': self.produto.id,
                'tipo_saida': 'VENDA',
                'quantidade': '1',
                'valor_venda_unitario': '40,00',
                'forma_pagamento_id': self.forma_credito.id,
                'parcelas': 12,
            },
        )
        self.assertEqual(response.status_code, 302)

        mov = MovimentoEstoqueSalao.objects.get(motivo=MovimentoEstoqueSalao.MOTIVO_VENDA)
        self.assertEqual(mov.taxa_percentual_aplicada, Decimal('0.00'))
        self.assertEqual(mov.valor_taxa, Decimal('0.00'))
        self.assertEqual(mov.valor_liquido_venda, Decimal('40.00'))

    def test_saida_uso_em_cliente_baixa_sem_receita(self):
        self._login()
        self.produto.saldo_atual = Decimal('4.000')
        self.produto.custo_medio_atual = Decimal('12.00')
        self.produto.save(update_fields=['saldo_atual', 'custo_medio_atual', 'atualizado_em'])

        response = self.client.post(
            reverse('salao:estoque'),
            {
                'action': 'create_saida_estoque',
                'ano': 2026,
                'mes': 3,
                'data': '2026-03-15',
                'produto_id': self.produto.id,
                'tipo_saida': 'USO_EM_CLIENTE',
                'quantidade': '1,5',
            },
        )
        self.assertEqual(response.status_code, 302)

        mov = MovimentoEstoqueSalao.objects.get(motivo=MovimentoEstoqueSalao.MOTIVO_USO_EM_CLIENTE)
        self.assertEqual(mov.valor_liquido_venda, Decimal('0.00'))
        self.assertEqual(mov.valor_custo_total, Decimal('18.00'))
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.saldo_atual, Decimal('2.500'))

    def test_saida_bloqueia_estoque_insuficiente(self):
        self._login()
        self.produto.saldo_atual = Decimal('1.000')
        self.produto.custo_medio_atual = Decimal('10.00')
        self.produto.save(update_fields=['saldo_atual', 'custo_medio_atual', 'atualizado_em'])

        response = self.client.post(
            reverse('salao:estoque'),
            {
                'action': 'create_saida_estoque',
                'ano': 2026,
                'mes': 3,
                'data': '2026-03-18',
                'produto_id': self.produto.id,
                'tipo_saida': 'USO_EM_CLIENTE',
                'quantidade': '2',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MovimentoEstoqueSalao.objects.count(), 0)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.saldo_atual, Decimal('1.000'))

    def test_dashboard_produto_separado_sem_comissao_de_produto(self):
        self._login()
        self._create_lancamento(
            data=date(2026, 3, 10),
            valor_bruto=Decimal('100.00'),
            forma_pagamento=self.forma_dinheiro,
            taxa_percentual=Decimal('0.00'),
        )
        MovimentoEstoqueSalao.objects.create(
            data=date(2026, 3, 11),
            produto=self.produto,
            tipo=MovimentoEstoqueSalao.TIPO_SAIDA,
            motivo=MovimentoEstoqueSalao.MOTIVO_VENDA,
            quantidade=Decimal('1.000'),
            custo_unitario_aplicado=Decimal('10.00'),
            valor_custo_total=Decimal('10.00'),
            valor_venda_unitario=Decimal('50.00'),
            valor_bruto_venda=Decimal('50.00'),
            taxa_percentual_aplicada=Decimal('0.00'),
            valor_taxa=Decimal('0.00'),
            valor_liquido_venda=Decimal('50.00'),
            lucro_produto=Decimal('40.00'),
            forma_pagamento=self.forma_dinheiro,
            parcelas=1,
        )

        response = self.client.get(reverse('salao:dashboard'), {'ano': 2026, 'mes': 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['comissao_calculada'], Decimal('20.00'))
        self.assertEqual(response.context['vendas_produto_liquidas'], Decimal('50.00'))
        self.assertEqual(response.context['lucro_produto'], Decimal('40.00'))

    def test_dashboard_agrupa_despesas_por_subcategoria(self):
        self._login()
        DespesaSalao.objects.create(
            data=date(2026, 3, 10),
            categoria=self.categoria,
            subcategoria=self.subcategoria,
            valor=Decimal('90.00'),
            observacao='Auxiliar',
        )
        response = self.client.get(reverse('salao:dashboard'), {'ano': 2026, 'mes': 3})
        self.assertEqual(response.status_code, 200)
        rows = list(response.context['despesas_por_subcategoria'])
        self.assertTrue(any(item['subcategoria_nome'] == self.subcategoria.nome for item in rows))

    def test_grid_lancamentos_filtra_por_servico_e_pagamento(self):
        self._login()
        outro_servico = ServicoSalao.objects.create(
            codigo='C99',
            nome='Outro Serviço',
            valor_padrao=Decimal('40.00'),
            ativo=True,
        )
        self._create_lancamento(
            data=date(2026, 3, 10),
            valor_bruto=Decimal('80.00'),
            forma_pagamento=self.forma_dinheiro,
            taxa_percentual=Decimal('0.00'),
        )
        LancamentoSalao.objects.create(
            data=date(2026, 3, 11),
            servico=outro_servico,
            forma_pagamento=self.forma_credito,
            parcelas=1,
            valor_bruto=Decimal('90.00'),
            taxa_percentual_aplicada=Decimal('4.00'),
            valor_taxa=Decimal('3.60'),
            valor_cobrado=Decimal('86.40'),
        )
        response = self.client.get(
            reverse('salao:grid_lancamentos'),
            {'ano': 2026, 'mes': 3, 'servico_id': self.servico.id, 'forma_pagamento_id': self.forma_dinheiro.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj'].object_list), 1)

    def test_grid_despesas_filtra_por_categoria_e_subcategoria(self):
        self._login()
        outra_categoria = CategoriaDespesaSalao.objects.create(nome='Fixos', ativo=True)
        DespesaSalao.objects.create(
            data=date(2026, 3, 9),
            categoria=self.categoria,
            subcategoria=self.subcategoria,
            valor=Decimal('70.00'),
        )
        DespesaSalao.objects.create(
            data=date(2026, 3, 9),
            categoria=outra_categoria,
            valor=Decimal('30.00'),
        )
        response = self.client.get(
            reverse('salao:grid_despesas'),
            {'ano': 2026, 'mes': 3, 'categoria_id': self.categoria.id, 'subcategoria_id': self.subcategoria.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj'].object_list), 1)

    def test_alerta_estoque_minimo_em_estoque_e_dashboard(self):
        self._login()
        self.produto.saldo_atual = Decimal('1.000')
        self.produto.estoque_minimo = Decimal('2.000')
        self.produto.save(update_fields=['saldo_atual', 'estoque_minimo', 'atualizado_em'])

        estoque_response = self.client.get(reverse('salao:estoque'), {'ano': 2026, 'mes': 3})
        self.assertEqual(estoque_response.status_code, 200)
        self.assertIn(self.produto, list(estoque_response.context['produtos_alerta']))

        dashboard_response = self.client.get(reverse('salao:dashboard'), {'ano': 2026, 'mes': 3})
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertIn(self.produto, list(dashboard_response.context['produtos_alerta']))
