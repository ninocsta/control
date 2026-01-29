# 🤖 AUTOMAÇÃO COMPLETA - Tasks Celery

## 📋 TODAS AS TASKS CONFIGURADAS

### 1️⃣ **PERÍODO FINANCEIRO** (infra.financeiro)

#### `task_gerar_periodo_mes_atual()`
- **Quando**: Dia 1 às 00:05
- **O que faz**: Cria PeriodoFinanceiro do mês atual
- **Idempotente**: Sim
- **Arquivo**: `infra/financeiro/tasks.py`

#### `task_fechar_periodo_mes_anterior()`
- **Quando**: Dia 1 às 02:00
- **O que faz**: 
  - Fecha PeriodoFinanceiro do mês anterior
  - Cria ContratoSnapshot para cada contrato ativo
  - Calcula custos rateados por contrato
  - Calcula margem e margem %
- **Idempotente**: Sim (não recalcula períodos já fechados)
- **Arquivo**: `infra/financeiro/tasks.py`

#### `task_alertar_vencimentos()`
- **Quando**: Diariamente às 08:00
- **O que faz**: Alerta custos de infraestrutura vencendo em 30/7/0 dias
- **Tipos**: Domínios, VPS, Emails
- **Arquivo**: `infra/financeiro/tasks.py`

---

### 2️⃣ **INVOICES** (invoices)

#### `task_gerar_invoices_mes_atual()`
- **Quando**: Dia 1 às 00:10
- **O que faz**:
  - Gera Invoice para cada cliente com contratos ativos
  - Soma valor_mensal de todos os contratos ativos
  - Define vencimento: dia 5 do mês
  - Status inicial: 'pendente'
- **Idempotente**: Sim (verifica se já existe)
- **Arquivo**: `invoices/tasks.py`

#### `task_marcar_invoices_atrasados()`
- **Quando**: Diariamente às 09:00
- **O que faz**: Marca invoices pendentes e vencidos como 'atrasado'
- **Arquivo**: `invoices/tasks.py`

---

## 📅 CRONOGRAMA COMPLETO

### **Todo Dia 1 do Mês:**

```
00:05 → Gerar Período Financeiro (mês atual)
         ↓
00:10 → Gerar Invoices (cobranças do mês)
         ↓
02:00 → Fechar Período Anterior (custos e snapshots)
```

### **Todos os Dias:**

```
08:00 → Alertar Vencimentos (infra)
09:00 → Marcar Invoices Atrasados
```

---

## 🔄 FLUXO DETALHADO (Exemplo: Janeiro 2026)

### **01/01/2026 às 00:05**
```
task_gerar_periodo_mes_atual()
→ Cria: PeriodoFinanceiro(mes=1, ano=2026, fechado=False)
```

### **01/01/2026 às 00:10**
```
task_gerar_invoices_mes_atual()
→ Para cada cliente ativo:
  1. Busca contratos ativos em 01/2026
  2. Soma valores dos contratos
  3. Cria Invoice(
       cliente=...,
       mes_referencia=1,
       ano_referencia=2026,
       valor_total=...,
       vencimento=05/01/2026,
       status='pendente'
     )
```

### **01/01/2026 às 02:00**
```
task_fechar_periodo_mes_anterior()
→ Fecha: PeriodoFinanceiro(mes=12, ano=2025)
→ Para cada contrato ativo em 12/2025:
  1. Calcula custos de infra rateados
  2. Cria ContratoSnapshot com receita/custos/margem
  3. Marca período como fechado
```

### **Diariamente às 08:00**
```
task_alertar_vencimentos()
→ Busca custos vencendo em 30/7/0 dias
→ Gera lista de alertas
→ TODO: Enviar email/notificação
```

### **Diariamente às 09:00**
```
task_marcar_invoices_atrasados()
→ Busca invoices pendentes com vencimento < hoje
→ Marca como 'atrasado'
→ TODO: Enviar cobrança
```

---

## 🚀 COMO EXECUTAR

### **Produção (Automático)**

1. **Rodar Worker:**
```bash
celery -A app worker --loglevel=info
```

2. **Rodar Beat (Agendador):**
```bash
celery -A app beat --loglevel=info
```

3. **Rodar ambos em background (Linux):**
```bash
# Worker
nohup celery -A app worker --loglevel=info > celery_worker.log 2>&1 &

# Beat
nohup celery -A app beat --loglevel=info > celery_beat.log 2>&1 &
```

### **Desenvolvimento (Manual)**

#### **Via Management Commands:**

```bash
# Gerar período
python manage.py criar_periodo --mes 1 --ano 2026

# Gerar invoices
python manage.py gerar_invoices
python manage.py gerar_invoices --mes 1 --ano 2026
python manage.py gerar_invoices --cliente "Nome Cliente"

# Fechar período
python manage.py fechar_periodo --mes 12 --ano 2025 --usuario "Admin"
```

#### **Via Django Shell:**

```python
from invoices.tasks import task_gerar_invoices_mes_atual
from infra.financeiro.tasks import task_gerar_periodo_mes_atual

# Executar tasks
task_gerar_periodo_mes_atual()
task_gerar_invoices_mes_atual()
```

#### **Via Celery (modo eager):**

```python
# settings.py (temporário)
CELERY_TASK_ALWAYS_EAGER = True

# Executar
from invoices.tasks import task_gerar_invoices_mes_atual
task_gerar_invoices_mes_atual.delay()
```

---

## 📊 EXEMPLO PRÁTICO

### **Dados Iniciais:**

**Clientes:**
- Cliente A (ativo)
- Cliente B (ativo)
- Cliente C (inativo)

**Contratos (Janeiro 2026):**
- Contrato 1: Cliente A, R$ 500/mês, data_inicio=01/01/2026
- Contrato 2: Cliente A, R$ 300/mês, data_inicio=15/12/2025
- Contrato 3: Cliente B, R$ 1000/mês, data_inicio=01/01/2025

**Custos de Infra (Janeiro 2026):**
- Domínio X: R$ 100/mês (vinculado a Contrato 1 e 2)
- VPS Y: R$ 200/mês (vinculado a Contrato 3)

---

### **Execução: 01/01/2026**

#### **00:05 - Período Financeiro:**
```
✅ Criado: PeriodoFinanceiro(mes=1, ano=2026)
```

#### **00:10 - Invoices:**
```
✅ Invoice #1: Cliente A - R$ 800,00 (Contratos 1 + 2) - Venc: 05/01/2026
✅ Invoice #2: Cliente B - R$ 1.000,00 (Contrato 3) - Venc: 05/01/2026
⚠️  Cliente C: Inativo, pulado
```

#### **02:00 - Fechamento (mês anterior: Dezembro/2025):**
```
✅ ContratoSnapshot #1:
   - Contrato: Contrato 2 (Cliente A)
   - Receita: R$ 300,00
   - Custo Domínios: R$ 50,00 (Domínio X rateado por 2)
   - Custo Total: R$ 50,00
   - Margem: R$ 250,00
   - Margem %: 83.33%

✅ PeriodoFinanceiro(mes=12, ano=2025) → FECHADO
```

---

## 📝 MANAGEMENT COMMANDS DISPONÍVEIS

```bash
# Período Financeiro
python manage.py criar_periodo --mes 1 --ano 2026
python manage.py fechar_periodo --mes 12 --ano 2025 --usuario "Admin"

# Invoices
python manage.py gerar_invoices
python manage.py gerar_invoices --mes 1 --ano 2026
python manage.py gerar_invoices --cliente "Nome do Cliente"
```

---

## 🔍 MONITORAMENTO

### **Logs do Celery:**
```bash
# Ver logs do worker
tail -f celery_worker.log

# Ver logs do beat
tail -f celery_beat.log
```

### **Django Admin:**
- `http://localhost:8000/admin/invoices/invoice/` - Ver invoices
- `http://localhost:8000/admin/financeiro/periodofinanceiro/` - Ver períodos
- `http://localhost:8000/admin/financeiro/contratosnapshot/` - Ver snapshots

### **Dashboard Financeiro:**
- `http://localhost:8000/financeiro/dashboard/` - Relatórios

---

## ⚠️ VALIDAÇÕES E PROTEÇÕES

### **Invoices:**
- ✅ Constraint unique: (cliente, mes_referencia, ano_referencia)
- ✅ Não cria se já existe
- ✅ Não cria se cliente sem contratos ativos
- ✅ Não cria se valor total = 0
- ✅ Transaction atomic

### **Período Financeiro:**
- ✅ Constraint unique: (mes, ano)
- ✅ Não recalcula se já fechado
- ✅ Signals impedem alteração de dados históricos
- ✅ Transaction atomic no fechamento

### **Snapshots:**
- ✅ Imutáveis (readonly no admin)
- ✅ Não podem ser deletados
- ✅ Constraint unique: (contrato, periodo)

---

## 📚 ARQUIVOS RELACIONADOS

```
app/
├── celery.py                          # Configuração Celery + Beat Schedule
├── settings.py                        # Configurações Celery
│
invoices/
├── models.py                          # Model Invoice
├── tasks.py                           # Tasks de invoice ⭐
├── admin.py                           # Admin customizado
└── management/commands/
    └── gerar_invoices.py              # Command manual
│
infra/financeiro/
├── models.py                          # PeriodoFinanceiro, ContratoSnapshot
├── tasks.py                           # Tasks financeiras
├── services/
│   ├── rateio.py                     # Lógica de rateio
│   └── fechamento_periodo.py         # Lógica de fechamento
└── management/commands/
    ├── criar_periodo.py
    └── fechar_periodo.py
```

---

## 🎯 PRÓXIMOS PASSOS (TODO)

### **Invoices:**
- [ ] Integração com gateway de pagamento (InfinitePay)
- [ ] Enviar email com boleto/link de pagamento
- [ ] Webhook para atualizar status ao pagar
- [ ] Notificação de invoices atrasados
- [ ] Relatório de inadimplência

### **Período Financeiro:**
- [ ] Email de resumo mensal para gestores
- [ ] Exportação de relatórios (PDF/Excel)
- [ ] Comparativo mês a mês

### **Alertas:**
- [ ] Sistema de notificações no admin
- [ ] Email de alertas de vencimento
- [ ] Dashboard de alertas

---

## 💡 DICAS

1. **Teste em desenvolvimento primeiro:**
   - Use `CELERY_TASK_ALWAYS_EAGER = True` no settings
   - Execute tasks manualmente via management commands

2. **Monitore os logs:**
   - Sempre revise os logs do Celery
   - Configure alertas para erros

3. **Backup antes de fechar período:**
   - Períodos fechados são imutáveis
   - Faça backup do banco antes

4. **Horários das tasks:**
   - Ajuste conforme necessário no `app/celery.py`
   - Use crontab syntax do Celery Beat

5. **Performance:**
   - Tasks usam select_related/prefetch_related
   - Otimize queries se volume aumentar
