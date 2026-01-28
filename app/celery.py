import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

app = Celery('app')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


# Configuração do Celery Beat
app.conf.beat_schedule = {
    'gerar-periodo-mes-atual': {
        'task': 'infra.financeiro.tasks.task_gerar_periodo_mes_atual',
        'schedule': crontab(day_of_month='1', hour='0', minute='5'),
        'options': {'expires': 3600}
    },
    'fechar-periodo-mes-anterior': {
        'task': 'infra.financeiro.tasks.task_fechar_periodo_mes_anterior',
        'schedule': crontab(day_of_month='1', hour='2', minute='0'),
        'options': {'expires': 3600}
    },
    'alertar-vencimentos-diario': {
        'task': 'infra.financeiro.tasks.task_alertar_vencimentos',
        'schedule': crontab(hour='8', minute='0'),
        'options': {'expires': 3600}
    },
}
