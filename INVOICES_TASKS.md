# 📄 Sistema de Invoices - Tasks Automatizadas

## ✅ O QUE FOI IMPLEMENTADO

### 📋 **Tasks de Invoices**

#### `invoices/tasks.py`

**1. `task_gerar_invoices_mes_atual()`**
- **Descrição**: Gera invoices de cobrança para todos os clientes com contratos ativos
- **Quando executa**: Todo dia 1 do mês às 00:10 (logo após criar o período financeiro)
- **Idempotente**: Não gera duplicatas, verifica se já existe invoice para o cliente no mês
- **Regras**:
  - 1 invoice por cliente por mês
  - Valor = soma dos contratos ativos no mês
  - Vencimento padrão: dia 5 do mês de referência
  - Status inicial: 'pendente'
  - Contratos ativos: `data_inicio <= primeiro_dia_mes` E (`data_fim null` OU `data_fim >= primeiro_dia_mes`)

**2. `task_marcar_invoices_atrasados()`**
- **Descrição**: Marca invoices como 'atrasado' quando passam do vencimento
- **Quando executa**: Diariamente às 09:00
- **Regras**:
  - Somente invoices com status 'pendente'
  - Vencimento < hoje
  - TODO: Enviar notificação/email para cobrança

---

## 🔄 FLUXO COMPLETO DE AUTOMAÇÃO

### **Dia 1 do mês:**

1. **00:05** - `task_gerar_periodo_mes_atual()`
   - Cria `PeriodoFinanceiro` do mês atual

2. **00:10** - `task_gerar_invoices_mes_atual()` ⭐ **NOVA**
   - Cria `Invoice` para cada cliente com contratos ativos
   - Calcula valor total somando contratos
   - Define vencimento para dia 5 do mês

3. **02:00** - `task_fechar_periodo_mes_anterior()`
   - Fecha `PeriodoFinanceiro` do mês anterior
   - Cria snapshots com custos rateados

### **Diariamente:**

4. **08:00** - `task_alertar_vencimentos()`
   - Alerta custos de infraestrutura vencendo em 30/7/0 dias

5. **09:00** - `task_marcar_invoices_atrasados()` ⭐ **NOVA**
   - Marca invoices pendentes e vencidos como 'atrasado'

---

## 📊 EXEMPLO DE EXECUÇÃO

### Cenário:
- **Cliente A**: 2 contratos ativos
  - Contrato 1: R$ 500,00/mês
  - Contrato 2: R$ 300,00/mês
- **Cliente B**: 1 contrato ativo
  - Contrato 3: R$ 1.000,00/mês
- **Cliente C**: Sem contratos ativos

### Resultado da task (01/02/2026):
```json
{
  "mes_referencia": "02/2026",
  "total_clientes": 3,
  "invoices_criados": 2,
  "invoices_existentes": 0,
  "clientes_sem_contrato": 1,
  "erros": 0,
  "detalhes": {
    "criados": [
      {
        "cliente": "Cliente A",
        "invoice_id": 1,
        "valor": 800.0,
        "contratos": ["Contrato 1", "Contrato 2"]
      },
      {
        "cliente": "Cliente B",
        "invoice_id": 2,
        "valor": 1000.0,
        "contratos": ["Contrato 3"]
      }
    ],
    "sem_contrato": ["Cliente C"]
  }
}
```

### Invoices criados:
- **Invoice #1**: Cliente A - R$ 800,00 - Vencimento: 05/02/2026 - Status: Pendente
- **Invoice #2**: Cliente B - R$ 1.000,00 - Vencimento: 05/02/2026 - Status: Pendente

---

## 🚀 COMO TESTAR

### 1. Testar manualmente via Django shell:
```python
from invoices.tasks import task_gerar_invoices_mes_atual

# Executar task
resultado = task_gerar_invoices_mes_atual()
print(resultado)
```

### 2. Testar via Celery (modo eager):
```python
# No settings.py temporariamente:
CELERY_TASK_ALWAYS_EAGER = True

# Depois executar:
from invoices.tasks import task_gerar_invoices_mes_atual
task_gerar_invoices_mes_atual.delay()
```

### 3. Verificar no admin:
1. Acesse `http://localhost:8000/admin/invoices/invoice/`
2. Veja os invoices criados automaticamente
3. Filtre por mês/ano de referência

---

## 📝 MANAGEMENT COMMAND (Opcional)

Você pode criar um comando Django para testar/executar manualmente:

```bash
# invoices/management/commands/gerar_invoices.py
from django.core.management.base import BaseCommand
from invoices.tasks import task_gerar_invoices_mes_atual

class Command(BaseCommand):
    help = 'Gera invoices do mês atual'

    def handle(self, *args, **options):
        resultado = task_gerar_invoices_mes_atual()
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ {resultado['invoices_criados']} invoices criados"
            )
        )
```

Uso:
```bash
python manage.py gerar_invoices
```

---

## ⚠️ IMPORTANTE

### Validações:
- ✅ Não cria invoices duplicados (constraint unique em cliente+mês+ano)
- ✅ Não cria invoice se cliente não tem contratos ativos
- ✅ Não cria invoice se valor total for zero
- ✅ Usa transaction.atomic() para garantir consistência

### Próximos passos (TODO):
- [ ] Integração com gateway de pagamento (InfinitePay)
- [ ] Enviar email com boleto/link de pagamento
- [ ] Notificação de invoices atrasados
- [ ] Webhook para marcar como pago
- [ ] Relatório mensal de inadimplência

---

## 📅 SCHEDULE COMPLETO

| Horário | Task | Descrição |
|---------|------|-----------|
| Dia 1 00:05 | `task_gerar_periodo_mes_atual` | Cria período financeiro |
| Dia 1 00:10 | `task_gerar_invoices_mes_atual` | Gera invoices de cobrança |
| Dia 1 02:00 | `task_fechar_periodo_mes_anterior` | Fecha período e cria snapshots |
| Diário 08:00 | `task_alertar_vencimentos` | Alerta vencimentos de infra |
| Diário 09:00 | `task_marcar_invoices_atrasados` | Marca invoices vencidos |

---

## 🔍 LOGS

Os logs podem ser visualizados durante execução do Celery:

```bash
# Worker
celery -A app worker --loglevel=info

# Beat
celery -A app beat --loglevel=info
```

Exemplos de logs:
```
[INFO] Invoice criado: Invoice Cliente A - 02/2026 - R$ 800,00 (2 contratos)
[INFO] Task concluída - 2 invoices criados, 0 já existiam, 1 sem contrato, 0 erros
[WARNING] Invoice 123 marcado como atrasado - Cliente XYZ - 3 dias
```
