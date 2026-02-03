"""
Management command para gerar invoices manualmente.

Uso:
    python manage.py gerar_invoices
    python manage.py gerar_invoices --mes 1 --ano 2026
"""
from django.core.management.base import BaseCommand, CommandError
from datetime import date
from invoices.models import Invoice, InvoiceContrato
from contratos.models import Contrato
from django.db import transaction, models


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

        # Clientes com invoice do período sem vínculo (evitar duplicação)
        invoices_sem_vinculo = Invoice.objects.filter(
            mes_referencia=mes,
            ano_referencia=ano,
            itens_contrato__isnull=True
        ).values_list('cliente_id', flat=True)
        clientes_com_invoice_sem_vinculo = set(invoices_sem_vinculo)

        # Buscar contratos ativos
        contratos = Contrato.objects.filter(
            data_inicio__lte=primeiro_dia_mes
        ).filter(
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=primeiro_dia_mes)
        ).select_related('cliente')
        
        if cliente_nome:
            contratos = contratos.filter(cliente__nome__icontains=cliente_nome)
            if not contratos.exists():
                raise CommandError(f'Cliente "{cliente_nome}" não encontrado')

        self.stdout.write(f'Total de contratos ativos: {contratos.count()}')

        invoices_criados = 0
        invoices_existentes = 0
        contratos_sem_invoice = 0
        erros = 0

        for contrato in contratos:
            try:
                # Evitar duplicação se já existe invoice sem vínculo para o cliente
                if contrato.cliente_id in clientes_com_invoice_sem_vinculo:
                    contratos_sem_invoice += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  {contrato.nome}: Cliente já possui invoice sem vínculo no período'
                        )
                    )
                    continue

                # Verificar se já existe invoice para este contrato neste mês
                invoice_existente = InvoiceContrato.objects.filter(
                    contrato=contrato,
                    invoice__mes_referencia=mes,
                    invoice__ano_referencia=ano
                ).select_related('invoice').first()

                if invoice_existente:
                    invoices_existentes += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  {contrato.nome}: Invoice já existe (#{invoice_existente.invoice.id})'
                        )
                    )
                    continue
                
                valor_total = contrato.valor_mensal

                if valor_total <= 0:
                    contratos_sem_invoice += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  {contrato.nome}: Valor total zerado'
                        )
                    )
                    continue

                # Criar invoice
                with transaction.atomic():
                    invoice = Invoice.objects.create(
                        cliente=contrato.cliente,
                        mes_referencia=mes,
                        ano_referencia=ano,
                        valor_total=valor_total,
                        vencimento=vencimento,
                        status='pendente'
                    )
                    
                    # Criar vínculos invoice ↔ contrato
                    InvoiceContrato.objects.create(
                        invoice=invoice,
                        contrato=contrato,
                        valor=contrato.valor_mensal
                    )

                    invoices_criados += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✅ {contrato.nome}: Invoice #{invoice.id} criado - '
                            f'R$ {valor_total:,.2f}'
                        )
                    )

            except Exception as e:
                erros += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'  ❌ {contrato.nome}: Erro - {str(e)}'
                    )
                )

        # Resumo
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('RESUMO:'))
        self.stdout.write(f'  Total de contratos: {contratos.count()}')
        self.stdout.write(
            self.style.SUCCESS(f'  ✅ Invoices criados: {invoices_criados}')
        )
        if invoices_existentes > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  Invoices já existentes: {invoices_existentes}')
            )
        if contratos_sem_invoice > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  Contratos sem invoice: {contratos_sem_invoice}')
            )
        if erros > 0:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Erros: {erros}')
            )
        self.stdout.write(self.style.SUCCESS('=' * 60))
