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

    @patch('invoices.views.task_enviar_confirmacao_imediata.delay')
    def test_webhook_remove_cobrancas_pendentes_e_mantem_confirmacao(self, delay_mock):
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

        resultado = task_processar_fila_waha.run(limite=10)

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

        resultado = task_processar_fila_waha.run(limite=10)

        self.assertEqual(resultado['processadas'], 1)
        self.assertEqual(resultado['enviadas'], 1)
        self.assertEqual(resultado['falhas'], 0)

        mensagem.refresh_from_db()
        self.assertEqual(mensagem.status, 'enviado')
        self.assertIn('venceu em', mensagem.mensagem)

        args, _ = send_message_mock.call_args
        self.assertEqual(args[0], self.cliente.telefone)
        self.assertIn('venceu em', args[1])
