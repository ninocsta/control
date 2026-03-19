from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import (
    CategoriaDespesaSalao,
    ComissaoMensalSalao,
    DespesaSalao,
    LancamentoSalao,
    ServicoSalao,
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

    def _login(self):
        self.client.force_login(self.superuser)

    def test_dashboard_auto_create_comissao(self):
        self._login()
        self.assertEqual(ComissaoMensalSalao.objects.count(), 0)

        response = self.client.get(reverse('salao:dashboard'), {'ano': 2026, 'mes': 2})

        self.assertEqual(response.status_code, 200)
        comissao = ComissaoMensalSalao.objects.get(ano=2026, mes=2)
        self.assertEqual(comissao.percentual, Decimal('20.00'))

    def test_dashboard_calculo_sem_override(self):
        self._login()

        LancamentoSalao.objects.create(
            data=date(2026, 3, 10),
            servico=self.servico,
            valor_cobrado=Decimal('200.00'),
        )
        LancamentoSalao.objects.create(
            data=date(2026, 3, 12),
            servico=self.servico,
            valor_cobrado=Decimal('100.00'),
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
        self.assertEqual(response.context['comissao_calculada'], Decimal('60.00'))
        self.assertEqual(response.context['comissao_paga'], Decimal('60.00'))
        self.assertEqual(response.context['despesas_total'], Decimal('50.00'))
        self.assertEqual(response.context['lucro'], Decimal('190.00'))
        self.assertIn('atendimentos_dia_chart', response.context)
        self.assertEqual(len(response.context['atendimentos_dia_chart']['labels']), 31)

    def test_dashboard_ignora_override_e_usa_comissao_automatica(self):
        self._login()

        LancamentoSalao.objects.create(
            data=date(2026, 3, 10),
            servico=self.servico,
            valor_cobrado=Decimal('300.00'),
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
        self.assertEqual(response.context['comissao_paga'], Decimal('60.00'))
        self.assertEqual(response.context['lucro'], Decimal('240.00'))

    def test_dashboard_salva_meta_e_calcula_percentual_atingido(self):
        self._login()

        LancamentoSalao.objects.create(
            data=date(2026, 3, 10),
            servico=self.servico,
            valor_cobrado=Decimal('500.00'),
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
        self.assertIn('ano=2026', post_response.url)
        self.assertIn('mes=3', post_response.url)

        response = self.client.get(reverse('salao:dashboard'), {'ano': 2026, 'mes': 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['meta_faturamento'], Decimal('1000.00'))
        self.assertEqual(response.context['percentual_meta_atingido'], Decimal('50.00'))
        self.assertEqual(response.context['valor_faltante_meta'], Decimal('500.00'))

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
                'valor_cobrado': '70,00',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(LancamentoSalao.objects.count(), 0)

    def test_lancamento_codigo_valido_salva_e_mantem_data(self):
        self._login()

        response = self.client.post(
            reverse('salao:lancamentos'),
            {
                'action': 'create_lancamento',
                'ano': 2026,
                'mes': 3,
                'dia': 10,
                'codigo': 'c01',
                'valor_cobrado': '80,00',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('ano=2026', response.url)
        self.assertIn('mes=3', response.url)
        self.assertIn('dia=10', response.url)
        self.assertEqual(LancamentoSalao.objects.count(), 1)
        self.assertEqual(LancamentoSalao.objects.first().data, date(2026, 3, 10))

    def test_trocar_competencia_preserva_dia_com_ajuste_de_limite(self):
        self._login()

        response = self.client.get(
            reverse('salao:lancamentos'),
            {
                'ano': 2026,
                'mes': 2,
                'dia': 31,
            },
        )
        self.assertEqual(response.status_code, 200)
        # Fevereiro/2026 possui 28 dias; dia é ajustado automaticamente.
        self.assertEqual(response.context['dia'], 28)

    def test_endpoint_resumo_lancamentos_por_dia(self):
        self._login()

        LancamentoSalao.objects.create(
            data=date(2026, 3, 10),
            servico=self.servico,
            valor_cobrado=Decimal('80.00'),
        )
        LancamentoSalao.objects.create(
            data=date(2026, 3, 10),
            servico=self.servico,
            valor_cobrado=Decimal('120.00'),
        )
        LancamentoSalao.objects.create(
            data=date(2026, 3, 12),
            servico=self.servico,
            valor_cobrado=Decimal('100.00'),
        )

        response = self.client.get(
            reverse('salao:lancamentos'),
            {
                'ano': 2026,
                'mes': 3,
                'dia': 10,
                'resumo': 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['dia'], 10)
        self.assertEqual(payload['resumo_dia']['qtd'], 2)
        self.assertEqual(payload['resumo_dia']['total'], 200.0)
        self.assertEqual(payload['resumo_mes']['qtd'], 3)
        self.assertEqual(payload['resumo_mes']['total'], 300.0)

    def test_editar_e_excluir_lancamento(self):
        self._login()

        lancamento = LancamentoSalao.objects.create(
            data=date(2026, 3, 10),
            servico=self.servico,
            valor_cobrado=Decimal('80.00'),
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
                'valor_cobrado': '95,00',
            },
        )
        self.assertEqual(edit_response.status_code, 302)

        lancamento.refresh_from_db()
        self.assertEqual(lancamento.data, date(2026, 3, 11))
        self.assertEqual(lancamento.valor_cobrado, Decimal('95.00'))

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
                'ordem': 3,
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
                'ordem': 5,
            },
        )
        self.assertEqual(update_response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.nome, 'Progressiva Premium')
        self.assertEqual(created.valor_padrao, Decimal('300.00'))
        self.assertFalse(created.ativo)

        delete_response = self.client.post(
            reverse('salao:servicos'),
            {
                'action': 'delete_servico',
                'servico_id': created.id,
            },
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(ServicoSalao.objects.filter(id=created.id).exists())

    def test_crud_categorias_pela_tela(self):
        self._login()

        create_response = self.client.post(
            reverse('salao:categorias'),
            {
                'action': 'create_categoria',
                'nome': 'Lavanderia',
                'ordem': 2,
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
                'ordem': 4,
            },
        )
        self.assertEqual(update_response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.nome, 'Lavanderia e Toalhas')
        self.assertEqual(created.ordem, 4)
        self.assertFalse(created.ativo)

        delete_response = self.client.post(
            reverse('salao:categorias'),
            {
                'action': 'delete_categoria',
                'categoria_id': created.id,
            },
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(CategoriaDespesaSalao.objects.filter(id=created.id).exists())
