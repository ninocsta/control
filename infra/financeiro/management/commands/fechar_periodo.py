"""
Management command para fechar período financeiro via linha de comando.

Uso:
    python manage.py fechar_periodo --mes 12 --ano 2025
    python manage.py fechar_periodo --mes 12 --ano 2025 --usuario "Admin Sistema"
"""
from django.core.management.base import BaseCommand, CommandError
from infra.financeiro.models import PeriodoFinanceiro
from infra.financeiro.services import fechar_periodo
from django.core.exceptions import ValidationError


class Command(BaseCommand):
    help = 'Fecha um período financeiro específico'

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
        parser.add_argument(
            '--usuario',
            type=str,
            default='Sistema (CLI)',
            help='Nome do usuário executando o fechamento'
        )

    def handle(self, *args, **options):
        mes = options['mes']
        ano = options['ano']
        usuario = options['usuario']
        
        # Validar mês
        if not 1 <= mes <= 12:
            raise CommandError('Mês deve estar entre 1 e 12')
        
        # Buscar período
        try:
            periodo = PeriodoFinanceiro.objects.get(mes=mes, ano=ano)
        except PeriodoFinanceiro.DoesNotExist:
            raise CommandError(f'Período {mes:02d}/{ano} não existe. Crie-o primeiro.')
        
        # Verificar se já está fechado
        if periodo.fechado:
            self.stdout.write(
                self.style.WARNING(
                    f'Período {periodo} já está fechado desde {periodo.fechado_em}'
                )
            )
            return
        
        # Fechar período
        self.stdout.write(f'Fechando período {periodo}...')
        
        try:
            resultado = fechar_periodo(periodo.id, usuario)
            
            self.stdout.write(self.style.SUCCESS('✓ Período fechado com sucesso!'))
            self.stdout.write(f"  Contratos processados: {resultado['contratos_processados']}")
            self.stdout.write(f"  Receita total: R$ {resultado['receita_total']:,.2f}")
            self.stdout.write(f"  Custo total: R$ {resultado['custo_total']:,.2f}")
            self.stdout.write(f"  Margem total: R$ {resultado['margem_total']:,.2f}")
            
        except ValidationError as e:
            raise CommandError(f'Erro de validação: {e}')
        except Exception as e:
            raise CommandError(f'Erro inesperado: {e}')
