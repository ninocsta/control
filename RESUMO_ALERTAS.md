# ✅ Sistema de Alertas de Vencimento - Implementado

## 🎯 O que foi implementado

Sistema completo de alertas por email para vencimentos de infraestrutura.

## 📝 Arquivos Modificados/Criados

### 1. `.env` - Configuração do Email de Alertas
```env
ALERT_EMAIL_RECIPIENT=nicolaskcdev@gmail.com
```

### 2. `app/settings.py` - Settings do Django
- Adicionado `EMAIL_USE_TLS = True`
- Adicionado `EMAIL_USE_SSL = False`
- Adicionado `DEFAULT_FROM_EMAIL`
- Adicionado `ALERT_EMAIL_RECIPIENT`

### 3. `infra/financeiro/tasks.py` - Task de Alertas
**Atualizada a task `task_alertar_vencimentos`:**
- ✅ Monitora **Domínios** (`DomainCost`)
- ✅ Monitora **VPS** (`VPSCost`)
- ✅ Monitora **Emails** (`DomainEmailCost`)
- ✅ Monitora **Hostings** (`HostingCost`) ← NOVO
- ✅ Monitora **Backups VPS** (`VPSBackupCost`) ← NOVO
- ✅ Envia email HTML formatado

**Nova função `enviar_email_alertas`:**
- Email com tabelas HTML coloridas
- Agrupamento por urgência (Hoje/7dias/30dias)
- Resumo financeiro completo
- Totalizadores

### 4. `app/celery.py` - Já Configurado
O schedule já estava correto:
```python
'alertar-vencimentos-diario': {
    'task': 'infra.financeiro.tasks.task_alertar_vencimentos',
    'schedule': crontab(hour='8', minute='0'),  # Diário às 08:00
}
```

### 5. `ALERTAS_VENCIMENTO.md` - Documentação Completa
Manual de uso, configuração e troubleshooting.

### 6. `test_alertas.py` - Script de Teste
Script para testar o sistema sem precisar esperar o Celery Beat.

## 🔔 Regras de Alerta

| Período | Cor | Urgência |
|---------|-----|----------|
| Hoje | 🔴 Vermelho | 🚨 Urgente |
| 7 dias | 🟠 Laranja | ⚠️ Atenção |
| 30 dias | 🔵 Azul | ℹ️ Informativo |

## 📧 Email Enviado Para

```
nicolaskcdev@gmail.com
```

**Para alterar:** Edite a variável `ALERT_EMAIL_RECIPIENT` no arquivo `.env`

## 🧪 Como Testar

### Opção 1: Script de Teste (Recomendado)
```bash
cd /home/nicolas/Documentos/github/control
source venv/bin/activate
python test_alertas.py
```

Este script irá:
1. ✅ Verificar todos os custos ativos
2. ✅ Listar vencimentos nos próximos 30 dias
3. ✅ Executar a task manualmente
4. ✅ Enviar email se houver vencimentos

### Opção 2: Django Shell
```python
from infra.financeiro.tasks import task_alertar_vencimentos
resultado = task_alertar_vencimentos()
print(resultado)
```

### Opção 3: Via Celery (em produção)
```bash
celery -A app call infra.financeiro.tasks.task_alertar_vencimentos
```

## 📊 Tipos de Custos Monitorados

| Tipo | Model | Inclui |
|------|-------|--------|
| 🌐 Domínios | `DomainCost` | Nome, fornecedor, valor |
| 💻 VPS | `VPSCost` | Nome, fornecedor, valor |
| 📧 Emails | `DomainEmailCost` | Domínio, cliente, contrato, fornecedor |
| 🌐 Hostings | `HostingCost` | Nome, fornecedor, valor |
| 💾 Backups | `VPSBackupCost` | Nome, VPS associada, fornecedor |

## 🕐 Quando Executa

**Automaticamente:** Todos os dias às 08:00 (horário de São Paulo)

Para verificar/modificar:
- Django Admin → **Periodic Tasks**
- Arquivo: `app/celery.py`

## ✅ Checklist de Funcionamento

- [x] Variável `ALERT_EMAIL_RECIPIENT` configurada no `.env`
- [x] Configuração SMTP válida (EMAIL_HOST, EMAIL_PORT, etc)
- [x] Task `task_alertar_vencimentos` implementada
- [x] Função `enviar_email_alertas` criada
- [x] Schedule do Celery Beat configurado
- [x] Imports atualizados (HostingCost, VPSBackupCost)
- [x] Script de teste criado
- [x] Documentação completa

## 🚀 Próximos Passos

1. **Testar o sistema:**
   ```bash
   python test_alertas.py
   ```

2. **Verificar email recebido** em `nicolaskcdev@gmail.com`

3. **Criar custos de teste** (se necessário):
   - Acesse Django Admin
   - Crie custos com vencimento hoje, +7 dias e +30 dias
   - Execute o teste novamente

4. **Colocar em produção:**
   - Garantir que Celery Worker e Beat estejam rodando
   - Verificar logs em `/var/log/celery/`

## 📚 Documentação

Consulte [ALERTAS_VENCIMENTO.md](ALERTAS_VENCIMENTO.md) para:
- Formato completo do email
- Troubleshooting detalhado
- Exemplos de uso
- Requisitos do sistema

## 🐛 Debug

Se o email não chegar:

1. **Verificar logs:**
   ```bash
   tail -f /var/log/celery/worker.log
   ```

2. **Testar SMTP:**
   ```python
   from django.core.mail import send_mail
   send_mail(
       'Teste',
       'Mensagem',
       'nicolas@costatech.dev',
       ['nicolaskcdev@gmail.com']
   )
   ```

3. **Verificar custos:**
   ```bash
   python test_alertas.py
   ```

## 💡 Dicas

- O email é **HTML formatado** com cores
- **Totalizadores** mostram impacto financeiro
- Sistema é **idempotente** (não duplica alertas)
- Funciona com **todos os tipos** de infraestrutura
- Pode ser configurado para **múltiplos destinatários** (futuramente)

---

**Status:** ✅ IMPLEMENTADO E PRONTO PARA TESTE

**Última atualização:** 30/01/2026
