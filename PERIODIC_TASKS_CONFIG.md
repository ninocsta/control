# 📋 Configuração de Periodic Tasks (Django Celery Beat)

## ⚠️ IMPORTANTE
As tarefas periódicas devem ser configuradas **via Django Admin**, não no código!

Acesse: `/admin/django_celery_beat/periodictask/`

---

## 🔄 Tarefas para Configurar

### 1️⃣ Gerar Período do Mês Atual
**Nome da Task:** `gerar-periodo-mes-atual`
- **Task (registered):** `infra.financeiro.tasks.task_gerar_periodo_mes_atual`
- **Tipo:** Crontab
- **Schedule:** 
  - Minute: `5`
  - Hour: `0`
  - Day of Month: `1`
  - Month of Year: `*` (todos)
  - Day of Week: `*` (todos)
- **Enabled:** ✅ Sim
- **Expires:** 3600 segundos (1 hora)
- **Descrição:** Cria o período financeiro do mês atual no dia 1 às 00:05

---

### 2️⃣ Gerar Invoices do Mês Atual
**Nome da Task:** `gerar-invoices-mes-atual`
- **Task (registered):** `invoices.tasks.task_gerar_invoices_mes_atual`
- **Tipo:** Crontab
- **Schedule:** 
  - Minute: `30`
  - Hour: `0`
  - Day of Month: `1`
  - Month of Year: `*`
  - Day of Week: `*`
- **Enabled:** ✅ Sim
- **Expires:** 3600 segundos
- **Descrição:** Gera invoices para todos os clientes com contratos ativos no dia 1 às 00:30

---

### 3️⃣ Fechar Período do Mês Anterior
**Nome da Task:** `fechar-periodo-mes-anterior`
- **Task (registered):** `infra.financeiro.tasks.task_fechar_periodo_mes_anterior`
- **Tipo:** Crontab
- **Schedule:** 
  - Minute: `0`
  - Hour: `2`
  - Day of Month: `1`
  - Month of Year: `*`
  - Day of Week: `*`
- **Enabled:** ✅ Sim
- **Expires:** 3600 segundos
- **Descrição:** Fecha o período financeiro do mês anterior no dia 1 às 02:00

---

### 4️⃣ Alertar Vencimentos (Diário)
**Nome da Task:** `alertar-vencimentos-diario`
- **Task (registered):** `infra.financeiro.tasks.task_alertar_vencimentos`
- **Tipo:** Crontab
- **Schedule:** 
  - Minute: `0`
  - Hour: `8`
  - Day of Month: `*` (todos)
  - Month of Year: `*`
  - Day of Week: `*`
- **Enabled:** ✅ Sim
- **Expires:** 3600 segundos
- **Descrição:** Envia alertas de vencimentos de infraestrutura diariamente às 08:00

---

### 5️⃣ Marcar Invoices Atrasados (Diário)
**Nome da Task:** `marcar-invoices-atrasados`
- **Task (registered):** `invoices.tasks.task_marcar_invoices_atrasados`
- **Tipo:** Crontab
- **Schedule:** 
  - Minute: `0`
  - Hour: `6`
  - Day of Month: `*` (todos)
  - Month of Year: `*`
  - Day of Week: `*`
- **Enabled:** ✅ Sim
- **Expires:** 3600 segundos
- **Descrição:** Marca invoices pendentes como atrasados quando passam do vencimento às 06:00

---

## 📝 Passo a Passo para Adicionar no Admin

1. **Acesse o Django Admin:** `/admin/`
2. **Navegue até:** `Django Celery Beat > Crontabs`
3. **Crie os Crontabs necessários** (se ainda não existirem):
   - `0 5 1 * *` (Dia 1 às 00:05)
   - `0 30 1 * *` (Dia 1 às 00:30)
   - `0 2 1 * *` (Dia 1 às 02:00)
   - `0 8 * * *` (Diário às 08:00)
   - `0 6 * * *` (Diário às 06:00)

4. **Navegue até:** `Django Celery Beat > Periodic tasks`
5. **Clique em "Add Periodic Task"**
6. **Preencha os campos conforme as especificações acima**
7. **Salve cada tarefa**

---

## 🧪 Como Testar

### 1. Verificar se as tasks estão registradas:
```bash
python manage.py shell
```

```python
from celery import current_app
tasks = current_app.tasks
for task in sorted(tasks.keys()):
    if 'infra.financeiro' in task or 'invoices.tasks' in task:
        print(task)
```

Deve exibir:
- `infra.financeiro.tasks.task_gerar_periodo_mes_atual`
- `infra.financeiro.tasks.task_fechar_periodo_mes_anterior`
- `infra.financeiro.tasks.task_alertar_vencimentos`
- `invoices.tasks.task_gerar_invoices_mes_atual`
- `invoices.tasks.task_marcar_invoices_atrasados`

### 2. Executar uma task manualmente:
```bash
# Via Django shell
python manage.py shell
```

```python
from infra.financeiro.tasks import task_gerar_periodo_mes_atual
resultado = task_gerar_periodo_mes_atual.delay()
print(resultado.get())
```

### 3. Verificar logs do Celery:
```bash
# No terminal onde o worker está rodando
# Você deve ver as tasks sendo executadas
```

---

## 🚀 Comandos para Produção

### Iniciar Celery Worker:
```bash
celery -A app worker --loglevel=info
```

### Iniciar Celery Beat:
```bash
celery -A app beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Com Supervisor (recomendado):
Criar arquivos de configuração em `/etc/supervisor/conf.d/`:

**celery_worker.conf:**
```ini
[program:celery_worker]
command=/caminho/para/venv/bin/celery -A app worker --loglevel=info
directory=/caminho/para/projeto
user=seu_usuario
numprocs=1
stdout_logfile=/var/log/celery/worker.log
stderr_logfile=/var/log/celery/worker_error.log
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
```

**celery_beat.conf:**
```ini
[program:celery_beat]
command=/caminho/para/venv/bin/celery -A app beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
directory=/caminho/para/projeto
user=seu_usuario
numprocs=1
stdout_logfile=/var/log/celery/beat.log
stderr_logfile=/var/log/celery/beat_error.log
autostart=true
autorestart=true
startsecs=10
```

---

## ✅ Checklist Final

- [ ] `django-celery-beat` instalado no requirements.txt
- [ ] `CELERY_BEAT_SCHEDULER` configurado no settings.py
- [ ] `django_celery_beat` em INSTALLED_APPS
- [ ] Migrations executadas: `python manage.py migrate`
- [ ] Periodic tasks criadas no Django Admin
- [ ] Redis rodando (broker)
- [ ] Celery worker rodando
- [ ] Celery beat rodando
- [ ] Tasks testadas manualmente
- [ ] Logs monitorados
- [ ] Supervisor configurado (para produção)

---

## 🔍 Troubleshooting

### Task não executa:
- Verificar se o beat scheduler está rodando
- Verificar se a task está **enabled** no admin
- Verificar logs do beat: `tail -f /var/log/celery/beat.log`
- Verificar timezone: `America/Sao_Paulo` no settings

### Task duplicada:
- Verificar se há múltiplos beats rodando
- Verificar no admin se não há tasks duplicadas

### Task não encontrada:
- Reiniciar worker após adicionar nova task
- Verificar se `autodiscover_tasks()` está no celery.py
- Verificar se o módulo está em INSTALLED_APPS

---

## 📊 Monitoramento

### Flower (opcional):
```bash
pip install flower
celery -A app flower
# Acesse: http://localhost:5555
```

### Verificar execuções no Admin:
`/admin/django_celery_beat/periodictasks/`

---

**Documentação oficial:** https://django-celery-beat.readthedocs.io/
