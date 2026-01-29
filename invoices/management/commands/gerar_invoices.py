"""
Management command para gerar invoices manualmente.

Uso:
    python manage.py gerar_invoices
    python manage.py gerar_invoices --mes 1 --ano 2026
"""
from django.core.management.base import BaseCommand, CommandError
from datetime import date
from invoices.tasks import task_gerar_invoices_mes_atual
from invoices.models import Invoice
from clientes.models import Cliente
from contratos.models import Contrato
from django.db import transaction, models
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Gera invoices de cobrança para clientes com contratos ativos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mes',
            type=int,
            help='Mês de referência (1-12). Padrão: mês atual'
        )
        parser.add_argument(
            '--ano',
            type=int,
            help='Ano de referência (ex: 2026). Padrão: ano atual'
        )
        parser.add_argument(
            '--cliente',
            type=str,
            help='Nome do cliente (opcional, gera apenas para este cliente)'
        )

    def handle(self, *args, **options):
        hoje = date.today()
        mes = options.get('mes') or hoje.month
        ano = options.get('ano') or hoje.year
        cliente_nome = options.get('cliente')

        # Validar mês
        if not 1 <= mes <= 12:
            raise CommandError('Mês deve estar entre 1 e 12')

        self.stdout.write(
            self.style.WARNING(
                f'Gerando invoices para {mes:02d}/{ano}...'
            )
        )

        # Vencimento padrão: dia 5 do mês
        vencimento = date(ano, mes, 5)
        primeiro_dia_mes = date(ano, mes, 1)

        # Buscar clientes
        if cliente_nome:
            clientes = Cliente.objects.filter(nome__icontains=cliente_nome, ativo=True)
            if not clientes.exists():
                raise CommandError(f'Cliente "{cliente_nome}" não encontrado')
        else:
            clientes = Cliente.objects.filter(ativo=True)

        self.stdout.write(f'Total de clientes ativos: {clientes.count()}')

        invoices_criados = 0
        invoices_existentes = 0
        clientes_sem_contrato = 0
        erros = 0

        for cliente in clientes:
            try:
                # Verificar se já existe
                invoice_existente = Invoice.objects.filter(
                    cliente=cliente,
                    mes_referencia=mes,
                    ano_referencia=ano
                ).first()

                if invoice_existente:
                    invoices_existentes += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  {cliente.nome}: Invoice já existe (#{invoice_existente.id})'
                        )
                    )
                    continue

                # Buscar contratos ativos
                contratos_ativos = Contrato.objects.filter(
                    cliente=cliente,
                    data_inicio__lte=primeiro_dia_mes
                ).filter(
                    models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia_mes)
                )

                if not contratos_ativos.exists():
                    clientes_sem_contrato += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  {cliente.nome}: Sem contratos ativos'
                        )
                    )
                    continue

                # Calcular valor total
                valor_total = sum(c.valor_mensal for c in contratos_ativos)

                if valor_total <= 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  {cliente.nome}: Valor total zerado'
                        )
                    )
                    continue

                # Criar invoice
                with transaction.atomic():
                    invoice = Invoice.objects.create(
                        cliente=cliente,
                        mes_referencia=mes,
                        ano_referencia=ano,
                        valor_total=valor_total,
                        vencimento=vencimento,
                        status='pendente'
                    )

                    invoices_criados += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✅ {cliente.nome}: Invoice #{invoice.id} criado - '
                            f'R$ {valor_total:,.2f} ({contratos_ativos.count()} contratos)'
                        )
                    )

            except Exception as e:
                erros += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'  ❌ {cliente.nome}: Erro - {str(e)}'
                    )
                )

        # Resumo
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('RESUMO:'))
        self.stdout.write(f'  Total de clientes: {clientes.count()}')
        self.stdout.write(
            self.style.SUCCESS(f'  ✅ Invoices criados: {invoices_criados}')
        )
        if invoices_existentes > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  Invoices já existentes: {invoices_existentes}')
            )
        if clientes_sem_contrato > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  Clientes sem contrato: {clientes_sem_contrato}')
            )
        if erros > 0:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Erros: {erros}')
            )
        self.stdout.write(self.style.SUCCESS('=' * 60))
