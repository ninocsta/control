# ⚡ QUICK REFERENCE - Tasks Automáticas

## 📅 SCHEDULE (quando cada task roda)

| Horário | Task | O que faz |
|---------|------|-----------|
| **Dia 1 - 00:05** | `task_gerar_periodo_mes_atual` | Cria período financeiro do mês |
| **Dia 1 - 00:10** | `task_gerar_invoices_mes_atual` | Gera cobranças para clientes |
| **Dia 1 - 02:00** | `task_fechar_periodo_mes_anterior` | Fecha mês anterior + snapshots |
| **Diário - 08:00** | `task_alertar_vencimentos` | Alerta vencimentos infra (30/7/0 dias) |
| **Diário - 09:00** | `task_marcar_invoices_atrasados` | Marca invoices vencidos |

## 🚀 COMANDOS ÚTEIS

### Rodar Celery
```bash
# Worker (processa tasks)
celery -A app worker --loglevel=info

# Beat (agendador)
celery -A app beat --loglevel=info

# Ambos em background
nohup celery -A app worker --loglevel=info > celery_worker.log 2>&1 &
nohup celery -A app beat --loglevel=info > celery_beat.log 2>&1 &
```

### Executar Manualmente
```bash
# Gerar período
python manage.py criar_periodo --mes 1 --ano 2026

# Gerar invoices
python manage.py gerar_invoices
python manage.py gerar_invoices --mes 1 --ano 2026

# Fechar período
python manage.py fechar_periodo --mes 12 --ano 2025 --usuario "Admin"
```

## 📊 FLUXO (Dia 1 do mês)

```
00:05 → Cria PeriodoFinanceiro(mes atual)
00:10 → Cria Invoices para clientes ativos
02:00 → Fecha PeriodoFinanceiro(mês anterior) + Snapshots
```

## 🔍 URLs Importantes

- Admin Invoices: `/admin/invoices/invoice/`
- Admin Períodos: `/admin/financeiro/periodofinanceiro/`
- Dashboard: `/financeiro/dashboard/`

## 📝 Regras Principais

**Invoice:**
- 1 por cliente por mês
- Valor = soma contratos ativos
- Vencimento = dia 5
- Status inicial = 'pendente'

**Contrato Ativo:**
- `data_inicio <= primeiro_dia_mes`
- `data_fim null` OU `data_fim >= primeiro_dia_mes`

## 📚 Arquivos Modificados

- ✅ `invoices/tasks.py` - Tasks de invoice (CRIADO)
- ✅ `invoices/management/commands/gerar_invoices.py` - Command (CRIADO)
- ✅ `app/celery.py` - Schedule atualizado
- ✅ `AUTOMACAO_COMPLETA.md` - Documentação completa (CRIADO)
- ✅ `INVOICES_TASKS.md` - Doc específica invoices (CRIADO)
