from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from contratos.models import Contrato
from infra.core.admin import somar_meses
from infra.financeiro.models import PeriodoFinanceiro
from infra.financeiro.services import fechar_periodo
from infra.financeiro.tasks import task_alertar_vencimentos
from infra.vps.models import VPS, VPSContrato, VPSCost


class InfraTests(TestCase):
    def setUp(self):
        cliente = Cliente.objects.create(nome='C', tipo='pessoa_juridica')
        self.contrato = Contrato.objects.create(
            cliente=cliente, nome='K', valor_mensal=Decimal('100'), data_inicio=date(2026, 1, 1),
        )
        self.vps = VPS.objects.create(nome='vps1', fornecedor='Hostinger')
        VPSContrato.objects.create(vps=self.vps, contrato=self.contrato, data_inicio=date(2026, 1, 1))

    def _cost(self, **kw):
        dados = dict(vps=self.vps, valor_total=Decimal('60'), periodo_meses=1,
                     data_inicio=date(2026, 1, 1), vencimento=date(2026, 12, 1))
        dados.update(kw)
        return VPSCost.objects.create(**dados)

    def test_custo_pago_pelo_cliente_fica_fora_do_fechamento(self):
        self._cost()
        self._cost(pago_pelo_cliente=True, valor_total=Decimal('999'))
        periodo = PeriodoFinanceiro.objects.create(mes=3, ano=2026)
        fechar_periodo(periodo.id, 'teste')
        snapshot = periodo.contrato_snapshots.get()
        self.assertEqual(snapshot.custo_vps, Decimal('60.00'))

    def test_encerrar_custo_depois_de_periodo_fechado_e_permitido(self):
        cost = self._cost()
        periodo = PeriodoFinanceiro.objects.create(mes=3, ano=2026)
        fechar_periodo(periodo.id, 'teste')

        cost.data_fim = date(2026, 6, 30)
        cost.full_clean()  # ok: março continua coberto

        cost.data_fim = date(2026, 2, 28)
        with self.assertRaises(ValidationError):
            cost.full_clean()

        cost.data_fim = None
        cost.valor_total = Decimal('80')
        with self.assertRaises(ValidationError):
            cost.full_clean()

    @patch('infra.financeiro.tasks.notify')
    def test_alerta_inclui_vencido_e_cliente_paga(self, notify_mock):
        hoje = timezone.localdate()
        self._cost(vencimento=hoje + timedelta(days=7), pago_pelo_cliente=True)
        self._cost(vencimento=hoje - timedelta(days=3))
        self._cost(vencimento=hoje + timedelta(days=8))
        resultado = task_alertar_vencimentos()
        self.assertEqual(resultado['total_alertas'], 2)
        texto = notify_mock.call_args[0][0]
        self.assertIn('cliente paga', texto)
        self.assertIn('vencido há 3d', texto)

    def test_somar_meses(self):
        self.assertEqual(somar_meses(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(somar_meses(date(2026, 11, 10), 12), date(2027, 11, 10))
