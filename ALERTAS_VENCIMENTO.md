# 🔔 Sistema de Alertas de Vencimento

## 📋 Visão Geral

Sistema automático de alertas por email para vencimentos de custos de infraestrutura, executado diariamente via Celery Beat.

## ⚙️ Configuração

### Variáveis de Ambiente (.env)

```env
# Email de Destino dos Alertas
ALERT_EMAIL_RECIPIENT=nicolaskcdev@gmail.com

# Configuração SMTP (necessária para envio)
EMAIL_HOST=smtp.hostinger.com
EMAIL_PORT=587
EMAIL_HOST_USER=nicolas@costatech.dev
EMAIL_HOST_PASSWORD=sua_senha_aqui
```

### Settings (app/settings.py)

```python
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = env('EMAIL_HOST_USER')
ALERT_EMAIL_RECIPIENT = env('ALERT_EMAIL_RECIPIENT')
```

## 📊 Tipos de Custos Monitorados

O sistema monitora todos os tipos de custos de infraestrutura:

1. **Domínios** (`DomainCost`)
   - Nome do domínio
   - Fornecedor
   
2. **VPS** (`VPSCost`)
   - Nome da VPS
   - Fornecedor

3. **Emails** (`DomainEmailCost`)
   - Domínio do email
   - Cliente e contrato associado
   - Fornecedor

4. **Hosting** (`HostingCost`)
   - Nome do hosting
   - Fornecedor

5. **Backups de VPS** (`VPSBackupCost`)
   - Nome do backup
   - VPS associada
   - Fornecedor

## 📅 Regras de Alerta

O sistema envia alertas em 3 momentos:

- **30 dias antes** do vencimento (ℹ️ Informativo - Azul)
- **7 dias antes** do vencimento (⚠️ Atenção - Laranja)
- **No dia do vencimento** (🚨 Urgente - Vermelho)

## 🕐 Agendamento

### Configuração no Celery Beat

A task é executada **diariamente às 08:00** (horário de São Paulo).

Para configurar via Django Admin:
1. Acesse **Periodic Tasks** no admin
2. Crie uma nova task:
   - **Task:** `infra.financeiro.tasks.task_alertar_vencimentos`
   - **Crontab:** `0 8 * * *` (08:00 todos os dias)
   - **Timezone:** `America/Sao_Paulo`

## 📧 Formato do Email

### Assunto
```
🔔 Alertas de Vencimento - X item(s) - DD/MM/YYYY
```

### Corpo (HTML)

O email contém:

1. **Cabeçalho**
   - Data de referência
   - Total de alertas

2. **Seções por Urgência**
   - 🚨 Vencendo HOJE (vermelho)
   - ⚠️ Vencendo em 7 DIAS (laranja)
   - ℹ️ Vencendo em 30 DIAS (azul)

3. **Tabelas com Informações**
   - Tipo do custo
   - Nome do recurso
   - Fornecedor
   - Data de vencimento
   - Valor

4. **Resumo Financeiro**
   - Quantidade e valor total por período
   - Total geral de todos os vencimentos

## 🔍 Exemplo de Email

```html
🔔 Alertas de Vencimento de Infraestrutura
Data: 30/01/2026
Total de Alertas: 5

🚨 VENCENDO HOJE (2)
┌──────────┬────────────────┬──────────────┬────────────┬──────────┐
│ Tipo     │ Nome           │ Fornecedor   │ Vencimento │ Valor    │
├──────────┼────────────────┼──────────────┼────────────┼──────────┤
│ Domínio  │ exemplo.com    │ HostGator    │ 30/01/2026 │ R$ 50,00 │
│ VPS      │ VPS-Web-01     │ DigitalOcean │ 30/01/2026 │ R$ 120,00│
└──────────┴────────────────┴──────────────┴────────────┴──────────┘

⚠️ VENCENDO EM 7 DIAS (2)
...

ℹ️ VENCENDO EM 30 DIAS (1)
...

💰 Resumo Financeiro
┌───────┬────────────┬─────────────┐
│ Hoje  │ 2          │ R$ 170,00   │
│ 7 dias│ 2          │ R$ 230,00   │
│ 30 dia│ 1          │ R$ 80,00    │
│ TOTAL │ 5          │ R$ 480,00   │
└───────┴────────────┴─────────────┘
```

## 🧪 Testar Manualmente

### Via Django Shell

```python
from infra.financeiro.tasks import task_alertar_vencimentos

# Executar task
resultado = task_alertar_vencimentos()
print(resultado)
```

### Via Celery

```bash
# Executar task imediatamente
celery -A app call infra.financeiro.tasks.task_alertar_vencimentos
```

## 📝 Logs

Logs são salvos em `/var/log/celery/` (produção) ou no console (desenvolvimento):

```
[INFO] Encontrados 5 vencimentos próximos
[INFO] Email de alertas enviado com sucesso para nicolaskcdev@gmail.com
```

ou

```
[INFO] Nenhum vencimento próximo encontrado
```

## ⚠️ Requisitos

1. **Celery e Redis** devem estar rodando:
   ```bash
   celery -A app worker -l info
   celery -A app beat -l info
   ```

2. **Configuração SMTP válida** no `.env`

3. **Custos cadastrados** com:
   - `ativo = True`
   - `vencimento` definido

## 🔧 Troubleshooting

### Email não enviado

1. Verificar configurações SMTP no `.env`
2. Testar conexão:
   ```python
   from django.core.mail import send_mail
   send_mail('Teste', 'Mensagem', 'from@email.com', ['to@email.com'])
   ```

3. Verificar logs do Celery para erros

### Alertas não aparecem

1. Verificar se há custos com vencimento nos próximos 30 dias
2. Verificar se custos estão com `ativo=True`
3. Executar task manualmente para debug

### Duplicação de Alertas

- A task é **idempotente**: cada custo gera apenas 1 alerta por dia
- Se executada várias vezes no mesmo dia, enviará emails duplicados
- Solução: garantir que o crontab esteja configurado corretamente

## 📚 Arquivos Relacionados

- [infra/financeiro/tasks.py](infra/financeiro/tasks.py) - Implementação das tasks
- [app/settings.py](app/settings.py) - Configurações de email
- [.env](.env) - Variáveis de ambiente
- [app/celery.py](app/celery.py) - Configuração do Celery

## 🎯 Próximas Melhorias

- [ ] Dashboard web para visualizar alertas
- [ ] Notificações via Telegram/Slack
- [ ] Relatório mensal de vencimentos
- [ ] Configuração de múltiplos destinatários
- [ ] Filtros personalizados (tipos de custo, fornecedor)
- [ ] Histórico de alertas enviados
