"""
Management command para gerar invoices manualmente.

Uso:
    python manage.py gerar_invoices
    python manage.py gerar_invoices --mes 1 --ano 2026
"""
from django.core.management.base import BaseCommand, CommandError
from datetime import date
from invoices.services.invoice_service import gerar_invoices_mensais


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

        resultado = gerar_invoices_mensais(mes=mes, ano=ano, cliente_nome=cliente_nome)

        if cliente_nome and resultado['total_clientes'] == 0:
            raise CommandError(f'Cliente \"{cliente_nome}\" não encontrado ou sem contratos ativos')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('RESUMO:'))
        self.stdout.write(f"  Total de clientes: {resultado['total_clientes']}")
        self.stdout.write(
            self.style.SUCCESS(f"  ✅ Invoices criados: {resultado['invoices_criados']}")
        )
        if resultado['invoices_existentes'] > 0:
            self.stdout.write(
                self.style.WARNING(f"  ⚠️  Invoices já existentes: {resultado['invoices_existentes']}")
            )
        if resultado['clientes_sem_contrato'] > 0:
            self.stdout.write(
                self.style.WARNING(f"  ⚠️  Clientes sem invoice: {resultado['clientes_sem_contrato']}")
            )
        if resultado['erros'] > 0:
            self.stdout.write(
                self.style.ERROR(f"  ❌ Erros: {resultado['erros']}")
            )
        self.stdout.write(self.style.SUCCESS('=' * 60))
