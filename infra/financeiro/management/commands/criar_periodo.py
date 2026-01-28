"""
Management command para criar período financeiro via linha de comando.

Uso:
    python manage.py criar_periodo --mes 1 --ano 2026
"""
from django.core.management.base import BaseCommand, CommandError
from infra.financeiro.models import PeriodoFinanceiro
from django.utils import timezone


class Command(BaseCommand):
    help = 'Cria um novo período financeiro'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mes',
            type=int,
            required=True,
            help='Mês do período (1-12)'
        )
        parser.add_argument(
            '--ano',
            type=int,
            required=True,
            help='Ano do período'
        )

    def handle(self, *args, **options):
        mes = options['mes']
        ano = options['ano']
        
        # Validar mês
        if not 1 <= mes <= 12:
            raise CommandError('Mês deve estar entre 1 e 12')
        
        # Criar período
        periodo, criado = PeriodoFinanceiro.objects.get_or_create(
            mes=mes,
            ano=ano,
            defaults={
                'fechado': False,
                'observacoes': f'Período criado via CLI em {timezone.now()}'
            }
        )
        
        if criado:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Período {periodo} criado com sucesso!')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠ Período {periodo} já existe')
            )
