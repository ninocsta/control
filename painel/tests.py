from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from contratos.models import Contrato, ContratoReajuste
from infra.recursos.models import CustoRecurso, Recurso, RecursoContrato
from invoices.models import Invoice, InvoiceContrato, MessageQueue


class PainelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('nico', password='x', is_staff=True)
        self.client.force_login(self.user)
        hoje = timezone.localdate()
        self.cliente = Cliente.objects.create(nome='Capta', telefone='5180475893', tipo='pessoa_juridica')
        self.contrato = Contrato.objects.create(
            cliente=self.cliente, nome='Sistema', valor_mensal=Decimal('500'), data_inicio=date(2026, 1, 1),
        )
        ContratoReajuste.objects.create(contrato=self.contrato, vigente_desde=hoje + timedelta(days=40),
                                        valor_mensal=Decimal('1500'))
        self.fatura = Invoice.objects.create(
            cliente=self.cliente, tipo='mensal', mes_referencia=hoje.month, ano_referencia=hoje.year,
            valor_total=Decimal('500'), vencimento=hoje - timedelta(days=2), status='atrasado',
            checkout_url='https://pay.example.com/x', order_nsu='1',
        )
        InvoiceContrato.objects.create(invoice=self.fatura, contrato=self.contrato, valor=Decimal('500'))
        self.vps = Recurso.objects.create(tipo='vps', nome='srv1', fornecedor='Hostinger')
        RecursoContrato.objects.create(recurso=self.vps, contrato=self.contrato, data_inicio=date(2026, 1, 1))
        self.custo = CustoRecurso.objects.create(
            recurso=self.vps, valor_total=Decimal('825.41'), periodo_meses=24, data_inicio=date(2026, 1, 1),
            vencimento=hoje + timedelta(days=5), pago_pelo_cliente=True,
        )

    def test_exige_staff(self):
        self.client.logout()
        self.assertRedirects(self.client.get('/'), '/login/?next=/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/login/').status_code, 200)

    def test_telas_abrem(self):
        hoje = timezone.localdate()
        urls = [
            reverse('painel:inicio'), reverse('painel:cobrancas'), reverse('painel:cobrancas') + '?mes=2026-11',
            reverse('painel:avulsa_nova'), reverse('painel:fatura', args=[self.fatura.pk]),
            reverse('painel:clientes'), reverse('painel:cliente', args=[self.cliente.pk]),
            reverse('painel:cliente_novo'), reverse('painel:cliente_editar', args=[self.cliente.pk]),
            reverse('painel:contrato_novo') + f'?cliente={self.cliente.pk}',
            reverse('painel:contrato_editar', args=[self.contrato.pk]),
            reverse('painel:agenda'), reverse('painel:agenda') + '?dias=365',
            reverse('painel:recursos'), reverse('painel:recursos') + '?tipo=vps&todos=1',
            reverse('painel:recurso', args=[self.vps.pk]), reverse('painel:recurso_novo'),
            reverse('painel:recurso_editar', args=[self.vps.pk]), reverse('painel:custo_editar', args=[self.custo.pk]),
            reverse('painel:financeiro'), reverse('painel:periodo', args=[hoje.year, hoje.month]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_inicio_mostra_atraso_e_agenda(self):
        r = self.client.get('/')
        self.assertContains(r, 'Capta')
        self.assertContains(r, 'Renovar VPS srv1')
        self.assertContains(r, 'R$ 500,00')

    @patch('painel.views.task_enviar_confirmacao_imediata')
    def test_recebi_via_htmx_devolve_linha(self, confirma):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(reverse('painel:fatura_acao', args=[self.fatura.pk, 'pagar']),
                                 {'pago_em': '2026-10-05'}, HTTP_HX_REQUEST='true')
        self.assertContains(r, 'pago')
        self.assertContains(r, 'hx-swap-oob')
        self.fatura.refresh_from_db()
        self.assertEqual(self.fatura.status, 'pago')
        self.assertEqual(timezone.localtime(self.fatura.pago_em).date(), date(2026, 10, 5))
        confirma.assert_called_once()

    def test_cancelar(self):
        MessageQueue.objects.create(invoice=self.fatura, telefone='1', mensagem='x', tipo='atraso',
                                    agendado_para=timezone.now())
        self.client.post(reverse('painel:fatura_acao', args=[self.fatura.pk, 'cancelar']))
        self.fatura.refresh_from_db()
        self.assertEqual(self.fatura.status, 'cancelado')
        self.assertFalse(MessageQueue.objects.exists())

    @patch('invoices.services.invoice_service.InfinitePayService.try_create_checkout')
    def test_avulsa(self, checkout):
        r = self.client.post(reverse('painel:avulsa_nova'), {
            'contrato': self.contrato.pk, 'descricao': 'Horas extras', 'valor': '320.00', 'vencimento': '2026-11-20'})
        avulsa = Invoice.objects.get(tipo='avulsa')
        self.assertRedirects(r, reverse('painel:fatura', args=[avulsa.pk]), fetch_redirect_response=False)
        self.assertEqual((avulsa.valor_total, avulsa.mes_referencia), (Decimal('320.00'), 11))
        checkout.assert_called_once()

    def test_mudar_vencimento_volta_pendente(self):
        novo = timezone.localdate() + timedelta(days=10)
        self.client.post(reverse('painel:fatura', args=[self.fatura.pk]), {'descricao': '', 'vencimento': novo})
        self.fatura.refresh_from_db()
        self.assertEqual((self.fatura.status, self.fatura.vencimento), ('pendente', novo))

    def test_renovar_custo(self):
        antes = self.custo.vencimento
        self.client.post(reverse('painel:custo_renovar', args=[self.custo.pk]), {'next': '/agenda/'})
        self.custo.refresh_from_db()
        self.assertEqual(self.custo.vencimento.year, antes.year + 2)

    def test_encerrar_contrato_desvincula_recursos(self):
        self.client.post(reverse('painel:contrato_encerrar', args=[self.contrato.pk]), {'data_fim': '2026-12-31'})
        self.contrato.refresh_from_db()
        self.assertEqual(self.contrato.data_fim, date(2026, 12, 31))
        self.assertEqual(RecursoContrato.objects.get().data_fim, date(2026, 12, 31))

    def test_reajuste_pelo_painel(self):
        self.client.post(reverse('painel:contrato_reajuste', args=[self.contrato.pk]),
                         {'vigente_desde': '2027-06-15', 'valor_mensal': '2000'})
        self.assertEqual(self.contrato.valor_em(date(2027, 6, 1)), Decimal('2000'))

    def test_novo_recurso_com_custo(self):
        r = self.client.post(reverse('painel:recurso_novo'), {
            'tipo': 'dominio', 'nome': 'exemplo.com.br', 'fornecedor': 'Registro.br', 'ativo': 'on',
            'custo-valor_total': '40', 'custo-periodo_meses': '12', 'custo-vencimento': '2027-03-01',
            'custo-data_inicio': '2026-03-01',
        })
        dominio = Recurso.objects.get(nome='exemplo.com.br')
        self.assertRedirects(r, reverse('painel:recurso', args=[dominio.pk]), fetch_redirect_response=False)
        self.assertEqual(dominio.custos.get().custo_mensal, Decimal('3.33'))

    def test_fechar_mes_pelo_painel(self):
        self.client.post(reverse('painel:periodo_fechar', args=[2026, 3]))
        from infra.financeiro.models import PeriodoFinanceiro
        self.assertTrue(PeriodoFinanceiro.objects.get(ano=2026, mes=3).fechado)
