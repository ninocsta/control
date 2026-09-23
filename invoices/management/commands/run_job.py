"""Roda um job periódico. É o que as Scheduled Tasks do Coolify chamam (ver DOCUMENTACAO_GERAL.md).

    python manage.py run_job processar_fila_waha
"""
from django.core.management.base import BaseCommand

from infra.financeiro import tasks as financeiro
from invoices import tasks as invoices

JOBS = {
    'gerar_invoices_mes_atual': invoices.task_gerar_invoices_mes_atual,
    'marcar_invoices_atrasados': invoices.task_marcar_invoices_atrasados,
    'agendar_mensagens_cobranca': invoices.task_agendar_mensagens_cobranca,
    'agendar_mensagens_atraso': invoices.task_agendar_mensagens_atraso,
    'processar_fila_waha': invoices.task_processar_fila_waha,
    'processar_checkouts_infinitepay': invoices.task_processar_checkouts_infinitepay,
    'gerar_periodo_mes_atual': financeiro.task_gerar_periodo_mes_atual,
    'fechar_periodo_mes_anterior': financeiro.task_fechar_periodo_mes_anterior,
    'alertar_vencimentos': financeiro.task_alertar_vencimentos,
}


class Command(BaseCommand):
    help = 'Roda um job periódico pelo nome.'

    def add_arguments(self, parser):
        parser.add_argument('job', choices=sorted(JOBS))

    def handle(self, *args, job, **options):
        self.stdout.write(f'{job}: {JOBS[job]()}')
