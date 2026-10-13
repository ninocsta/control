import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from invoices.models import Invoice, MessageQueue
from invoices.services.message_queue_service import montar_mensagem_cobranca
from invoices.tasks import task_processar_fila_waha


class InvoicesMessageTemplateTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nome='Cliente Teste',
            email='cliente-template@example.com',
            telefone='11999999999',
            tipo='pessoa_juridica',
            descricao_cobranca='Plano mensal',
        )
        self.invoice = Invoice.objects.create(
            cliente=self.cliente,
            mes_referencia=3,
            ano_referencia=2026,
            valor_total=Decimal('199.90'),
            vencimento=timezone.localdate(),
            status='pendente',
            checkout_url='https://pay.example.com/i/1',
        )

    def test_mensagem_no_dia_mantem_hoje_quando_data_referencia_igual_ao_vencimento(self):
        mensagem = montar_mensagem_cobranca(
            self.invoice,
            'no_dia',
            data_referencia=self.invoice.vencimento,
        )

        self.assertIn('vence *hoje', mensagem)

    def test_mensagem_no_dia_usa_venceu_em_quando_data_referencia_posterior(self):
        mensagem = montar_mensagem_cobranca(
            self.invoice,
            'no_dia',
            data_referencia=self.invoice.vencimento + timedelta(days=1),
        )

        self.assertIn('venceu em', mensagem)
        self.assertIn(self.invoice.vencimento.strftime('%d/%m/%Y'), mensagem)


class InvoicesWebhookQueueCleanupTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nome='Cliente Webhook',
            email='cliente-webhook@example.com',
            telefone='11988888888',
            tipo='pessoa_juridica',
        )
        self.invoice = Invoice.objects.create(
            cliente=self.cliente,
            mes_referencia=3,
            ano_referencia=2026,
            valor_total=Decimal('350.00'),
            vencimento=timezone.localdate(),
            status='pendente',
            checkout_url='https://pay.example.com/i/2',
            order_nsu='ORDER-123',
        )

    @patch('invoices.views.InfinitePayService.verificar_pagamento', return_value={'paid': True, 'paid_amount': 35000})
    @patch('invoices.views.task_enviar_confirmacao_imediata')
    def test_webhook_remove_cobrancas_pendentes_e_mantem_confirmacao(self, delay_mock, check_mock):
        cobranca = MessageQueue.objects.create(
            invoice=self.invoice,
            telefone=self.cliente.telefone,
            mensagem='Mensagem de cobrança',
            tipo='no_dia',
            agendado_para=timezone.now(),
            status='pendente',
        )
        confirmacao = MessageQueue.objects.create(
            invoice=self.invoice,
            telefone=self.cliente.telefone,
            mensagem='Mensagem de confirmação',
            tipo='confirmacao',
            agendado_para=timezone.now(),
            status='pendente',
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('invoices:infinitepay_webhook'),
                data=json.dumps({'order_nsu': self.invoice.order_nsu}),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'pago')
        self.assertFalse(MessageQueue.objects.filter(pk=cobranca.pk).exists())
        self.assertTrue(MessageQueue.objects.filter(pk=confirmacao.pk).exists())
        delay_mock.assert_called_once_with(confirmacao.id)
        self.assertIsNotNone(self.invoice.pago_em)

    @patch('invoices.views.notify')
    @patch('invoices.views.InfinitePayService.verificar_pagamento', return_value={'paid': False})
    def test_webhook_baixa_mas_avisa_se_infinitepay_nao_confirma(self, check_mock, notify_mock):
        response = self.client.post(
            reverse('invoices:infinitepay_webhook'),
            data=json.dumps({'order_nsu': self.invoice.order_nsu}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'pago')
        self.assertIn('NÃO está paga', notify_mock.call_args[0][0])

    @patch('invoices.views.notify')
    @patch('invoices.views.InfinitePayService.verificar_pagamento', side_effect=RuntimeError('timeout'))
    def test_webhook_baixa_mesmo_sem_conseguir_conferir(self, check_mock, notify_mock):
        response = self.client.post(
            reverse('invoices:infinitepay_webhook'),
            data=json.dumps({'order_nsu': self.invoice.order_nsu}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'pago')
        notify_mock.assert_called_once()

    def test_link_curto_de_fatura_paga_ou_cancelada_nao_leva_ao_checkout(self):
        self.invoice.status = 'cancelado'
        self.invoice.save()
        response = self.client.get(f'/p/{self.invoice.order_nsu}/')
        self.assertEqual(response.status_code, 410)


class InvoicesWahaQueueProcessingTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nome='Cliente Fila',
            email='cliente-fila@example.com',
            telefone='11977777777',
            tipo='pessoa_juridica',
        )

    @patch('invoices.tasks.WahaService.send_message')
    def test_task_remove_cobranca_pendente_quando_invoice_ja_pago(self, send_message_mock):
        invoice = Invoice.objects.create(
            cliente=self.cliente,
            mes_referencia=3,
            ano_referencia=2026,
            valor_total=Decimal('120.00'),
            vencimento=timezone.localdate(),
            status='pago',
            checkout_url='https://pay.example.com/i/3',
        )
        mensagem = MessageQueue.objects.create(
            invoice=invoice,
            telefone=self.cliente.telefone,
            mensagem='Cobrança antiga',
            tipo='2_dias',
            agendado_para=timezone.now() - timedelta(minutes=5),
            status='pendente',
        )

        resultado = task_processar_fila_waha(limite=10)

        self.assertEqual(resultado['processadas'], 1)
        self.assertEqual(resultado['enviadas'], 0)
        self.assertEqual(resultado['falhas'], 0)
        self.assertFalse(MessageQueue.objects.filter(pk=mensagem.pk).exists())
        send_message_mock.assert_not_called()

    @patch('invoices.tasks.WahaService.send_message', return_value={'status': 'ok'})
    def test_task_reconstroi_texto_no_dia_dinamicamente_no_envio(self, send_message_mock):
        vencimento = timezone.localdate() - timedelta(days=1)
        invoice = Invoice.objects.create(
            cliente=self.cliente,
            mes_referencia=3,
            ano_referencia=2026,
            valor_total=Decimal('180.00'),
            vencimento=vencimento,
            status='pendente',
            checkout_url='https://pay.example.com/i/4',
        )
        mensagem_original = montar_mensagem_cobranca(
            invoice,
            'no_dia',
            data_referencia=vencimento,
        )
        mensagem = MessageQueue.objects.create(
            invoice=invoice,
            telefone=self.cliente.telefone,
            mensagem=mensagem_original,
            tipo='no_dia',
            agendado_para=timezone.now() - timedelta(minutes=5),
            status='pendente',
        )

        resultado = task_processar_fila_waha(limite=10)

        self.assertEqual(resultado['processadas'], 1)
        self.assertEqual(resultado['enviadas'], 1)
        self.assertEqual(resultado['falhas'], 0)

        mensagem.refresh_from_db()
        self.assertEqual(mensagem.status, 'enviado')
        self.assertIn('venceu em', mensagem.mensagem)

        args, _ = send_message_mock.call_args
        self.assertEqual(args[0], self.cliente.telefone)
        self.assertIn('venceu em', args[1])

    @patch('invoices.tasks.time.sleep')
    @patch('invoices.tasks.WahaService.send_message', return_value={'status': 'ok'})
    def test_task_espaca_envios(self, send_message_mock, sleep_mock):
        for mes in (1, 2, 3):
            invoice = Invoice.objects.create(
                cliente=self.cliente,
                mes_referencia=mes,
                ano_referencia=2026,
                valor_total=Decimal('100.00'),
                vencimento=timezone.localdate(),
                status='pendente',
                checkout_url=f'https://pay.example.com/i/{mes}',
            )
            MessageQueue.objects.create(
                invoice=invoice,
                telefone=self.cliente.telefone,
                mensagem='x',
                tipo='no_dia',
                agendado_para=timezone.now() - timedelta(minutes=5),
                status='pendente',
            )

        resultado = task_processar_fila_waha(limite=10)

        self.assertEqual(resultado['enviadas'], 3)
        self.assertEqual(sleep_mock.call_count, 2)
        for chamada in sleep_mock.call_args_list:
            self.assertGreaterEqual(chamada.args[0], 30)


class InfinitePayServiceConfigTests(TestCase):
    @patch.dict('os.environ', {'INFINITEPAY_BASE_URL': '', 'INFINITEPAY_ITEM_DESCRIPTION': ''})
    def test_env_vazia_usa_defaults(self):
        # docker-compose passa ${VAR:-} como string vazia, não como ausente
        from invoices.services.infinitepay_service import InfinitePayService

        service = InfinitePayService()

        self.assertEqual(service.base_url, 'https://api.checkout.infinitepay.io')
        self.assertEqual(service.description, 'Mensalidade de serviços contratados')


class GerarInvoicesTests(TestCase):
    def setUp(self):
        from contratos.models import Contrato
        self.Contrato = Contrato
        self.cliente = Cliente.objects.create(
            nome='Capta Teste', telefone='11966666666', tipo='pessoa_juridica', vencimento_padrao=10,
        )

    def _gerar(self, mes, ano):
        from invoices.services.invoice_service import gerar_invoices_mensais
        with patch('invoices.services.invoice_service.InfinitePayService.try_create_checkout'):
            return gerar_invoices_mensais(mes=mes, ano=ano)

    def test_reajuste_programado_muda_valor_no_mes(self):
        from datetime import date
        from contratos.models import ContratoReajuste
        contrato = self.Contrato.objects.create(
            cliente=self.cliente, nome='Sistema', valor_mensal=Decimal('500'), data_inicio=date(2026, 11, 1),
        )
        ContratoReajuste.objects.create(contrato=contrato, vigente_desde=date(2027, 1, 15), valor_mensal=Decimal('1500'))

        self._gerar(10, 2026)
        self._gerar(12, 2026)
        self._gerar(1, 2027)

        valores = {
            (i.mes_referencia, i.ano_referencia): i.valor_total
            for i in Invoice.objects.filter(cliente=self.cliente)
        }
        self.assertEqual(valores, {(12, 2026): Decimal('500'), (1, 2027): Decimal('1500')})

    def test_contrato_no_meio_do_mes_cobra_so_no_seguinte(self):
        from datetime import date
        self.Contrato.objects.create(
            cliente=self.cliente, nome='Site', valor_mensal=Decimal('300'), data_inicio=date(2026, 10, 15),
        )
        self._gerar(10, 2026)
        self.assertFalse(Invoice.objects.filter(cliente=self.cliente, mes_referencia=10).exists())
        self._gerar(11, 2026)
        self.assertTrue(Invoice.objects.filter(cliente=self.cliente, mes_referencia=11).exists())

    def test_idempotente_por_contrato_e_avulsa_nao_bloqueia(self):
        from datetime import date
        from invoices.models import InvoiceContrato
        c1 = self.Contrato.objects.create(
            cliente=self.cliente, nome='A', valor_mensal=Decimal('100'), data_inicio=date(2026, 1, 1),
        )
        avulsa = Invoice.objects.create(
            cliente=self.cliente, tipo='avulsa', mes_referencia=11, ano_referencia=2026,
            valor_total=Decimal('80'), vencimento=date(2026, 11, 20),
        )
        InvoiceContrato.objects.create(invoice=avulsa, contrato=c1, valor=Decimal('80'))

        self._gerar(11, 2026)
        self.assertEqual(Invoice.objects.filter(tipo='mensal', mes_referencia=11).count(), 1)

        # contrato novo cadastrado depois, retroativo ao dia 1: entra numa fatura própria
        self.Contrato.objects.create(
            cliente=self.cliente, nome='B', valor_mensal=Decimal('50'), data_inicio=date(2026, 11, 1),
        )
        self._gerar(11, 2026)
        self._gerar(11, 2026)
        mensais = Invoice.objects.filter(tipo='mensal', mes_referencia=11).order_by('id')
        self.assertEqual([i.valor_total for i in mensais], [Decimal('100'), Decimal('50')])

    def test_mensalidade_cancelada_nao_volta(self):
        from datetime import date
        self.Contrato.objects.create(
            cliente=self.cliente, nome='A', valor_mensal=Decimal('100'), data_inicio=date(2026, 1, 1),
        )
        self._gerar(11, 2026)
        Invoice.objects.update(status='cancelado')
        self._gerar(11, 2026)
        self.assertEqual(Invoice.objects.count(), 1)


class RegistrarPagamentoTests(TestCase):
    def test_pagamento_manual_preenche_pago_em_e_agenda_confirmacao(self):
        from invoices.services.invoice_service import registrar_pagamento
        cliente = Cliente.objects.create(nome='X', telefone='11955555555', tipo='pessoa_fisica')
        invoice = Invoice.objects.create(
            cliente=cliente, mes_referencia=11, ano_referencia=2026,
            valor_total=Decimal('10'), vencimento=timezone.localdate(), status='atrasado',
        )
        MessageQueue.objects.create(
            invoice=invoice, telefone='1', mensagem='x', tipo='atraso', agendado_para=timezone.now(),
        )
        mensagem = registrar_pagamento(invoice, capture_method='manual')
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'pago')
        self.assertIsNotNone(invoice.pago_em)
        self.assertEqual(mensagem.tipo, 'confirmacao')
        self.assertFalse(MessageQueue.objects.filter(tipo='atraso').exists())


class FilaDescartaLembreteVencidoTests(TestCase):
    @patch('invoices.tasks.WahaService.send_message')
    def test_lembrete_5_dias_depois_do_vencimento_e_descartado(self, send_mock):
        cliente = Cliente.objects.create(nome='Y', telefone='11944444444', tipo='pessoa_fisica')
        invoice = Invoice.objects.create(
            cliente=cliente, mes_referencia=11, ano_referencia=2026, valor_total=Decimal('10'),
            vencimento=timezone.localdate() - timedelta(days=1), status='atrasado',
            checkout_url='https://pay.example.com/x',
        )
        MessageQueue.objects.create(
            invoice=invoice, telefone='1', mensagem='x', tipo='5_dias',
            agendado_para=timezone.now() - timedelta(days=6),
        )
        resultado = task_processar_fila_waha()
        send_mock.assert_not_called()
        self.assertEqual(resultado['descartadas'], 1)
        self.assertFalse(MessageQueue.objects.exists())


class InvoiceAdminTests(TestCase):
    def setUp(self):
        from datetime import date
        from django.contrib.auth.models import User
        from contratos.models import Contrato
        self.client.force_login(User.objects.create_superuser('admin', 'a@a.com', 'x'))
        self.cliente = Cliente.objects.create(nome='Z', telefone='11933333333', tipo='pessoa_fisica')
        self.contrato = Contrato.objects.create(
            cliente=self.cliente, nome='Z1', valor_mensal=Decimal('100'), data_inicio=date(2026, 1, 1),
        )

    @patch('invoices.services.invoice_service.InfinitePayService.try_create_checkout')
    @patch('invoices.tasks.WahaService.send_message')
    def test_avulsa_soma_itens_e_pagamento_manual_confirma(self, send_mock, checkout_mock):
        dados = {
            'cliente': self.cliente.id, 'tipo': 'avulsa', 'mes_referencia': 11, 'ano_referencia': 2026,
            'descricao': 'Horas extras', 'vencimento': '2026-11-20', 'status': 'pendente', 'pago_em_0': '', 'pago_em_1': '',
            'itens_contrato-TOTAL_FORMS': 1, 'itens_contrato-INITIAL_FORMS': 0,
            'itens_contrato-0-contrato': self.contrato.id, 'itens_contrato-0-valor': '250.00',
        }
        response = self.client.post('/admin/invoices/invoice/add/', dados)
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['errors'])
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.valor_total, Decimal('250.00'))

        item = invoice.itens_contrato.get()
        dados.update({
            'status': 'pago', 'itens_contrato-INITIAL_FORMS': 1, 'itens_contrato-0-id': item.id,
            'itens_contrato-0-invoice': invoice.id,
        })
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/admin/invoices/invoice/{invoice.id}/change/', dados)
        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertIsNotNone(invoice.pago_em)
        send_mock.assert_called_once()
        self.assertIn('Pagamento Confirmado', send_mock.call_args[0][1])
