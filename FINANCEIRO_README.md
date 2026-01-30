# 📊 Sistema Financeiro - Controle de Custos e Fechamento Mensal

## ✅ O QUE FOI IMPLEMENTADO

### 1️⃣ **Services (Lógica de Negócio)**

#### `infra/financeiro/services/rateio.py`
- **`calcular_custo_mensal(cost_object)`**: Calcula custo mensal de qualquer InfraCostModel
- **`ratear_por_contratos(valor, contratos)`**: Divide valor igualmente entre N contratos
- **`validar_periodo(periodo)`**: Valida se período pode ser fechado

#### `infra/financeiro/services/fechamento_periodo.py`
- **`fechar_periodo(periodo_id, usuario)`**: Função principal de fechamento
  - ✓ Valida período não fechado
  - ✓ Busca contratos ativos no mês (data_inicio <= período <= data_fim)
  - ✓ Coleta custos ativos (domínios, hostings, vps, backups, emails)
  - ✓ Faz rateio proporcional por contrato
  - ✓ Cria 1 snapshot por contrato
  - ✓ Preenche receita, custos, margem e detalhamento JSON
  - ✓ Marca período como fechado
  - ✓ Tudo em `transaction.atomic()`

---

### 2️⃣ **Celery + Celery Beat (Automação)**

#### `infra/financeiro/tasks.py`
- **`task_gerar_periodo_mes_atual()`**: Cria período do mês automaticamente
- **`task_fechar_periodo_mes_anterior()`**: Fecha mês anterior (se não fechado)
- **`task_alertar_vencimentos()`**: Alerta custos vencendo em 30/7/0 dias

#### `app/celery.py`
- Configurado Celery Beat com 3 schedules:
  - **Dia 1 às 00:05**: Gerar período do mês
  - **Dia 1 às 02:00**: Fechar mês anterior
  - **Diariamente às 08:00**: Alertar vencimentos

**Executar Celery:**
```bash
# Worker
celery -A app worker --loglevel=info

# Beat (agendador)
celery -A app beat --loglevel=info
```

---

### 3️⃣ **Django Admin Customizado**

#### **Clientes**
- Inline de contratos (readonly)
- Filtros por tipo e status

#### **Contratos**
- Inline de snapshots (readonly, não deletável)
- Campos calculados:
  - `custo_medio`: Média dos snapshots
  - `margem_media`: Margem % média
  - `total_snapshots`: Quantidade de períodos
  - `is_ativo`: Badge se contrato está ativo

#### **PeriodoFinanceiro**
- **Botão "Fechar Período"** (custom action)
- Status badge (Aberto/Fechado)
- Estatísticas calculadas:
  - Total de contratos
  - Receita total
  - Custo total
  - Margem total e %
- **Bloqueio de edição** quando fechado
- Inline de snapshots

#### **Infraestrutura (Domínio, Hosting, VPS, Backup, Email)**
- Inline de custos
- Mostra custo mensal calculado
- Filter_horizontal para contratos (M2M)
- Campo `custo_atual` na listagem

#### **ContratoSnapshot**
- Todos os campos readonly
- **Não pode criar** (só via fechamento)
- **Não pode deletar** (imutável)

---

### 4️⃣ **Dashboard Financeiro**

**URL:** `/financeiro/dashboard/`

**Mostra:**
- Cards de resumo: Receita, Custo, Margem, Margem %
- Tabela: Receita e custo por mês (últimos 12 períodos)
- Top 10 contratos mais lucrativos
- Custos por categoria (domínios, hostings, vps, backups, emails)

**Acesso:** Somente staff (`@staff_member_required`)

---

### 5️⃣ **Validações e Proteções**

#### `infra/financeiro/signals.py`
- **Não permitir reabrir período fechado**
- **Não permitir excluir snapshots** (imutáveis)
- **Não permitir alterar custos** se houver período fechado que dependa dele
  - Solução: Criar novo registro com `data_inicio` futura

#### Management Commands
```bash
# Criar período
python manage.py criar_periodo --mes 1 --ano 2026

# Fechar período
python manage.py fechar_periodo --mes 12 --ano 2025 --usuario "Admin"
```

---

### 6️⃣ **Otimizações**

- **`select_related` / `prefetch_related`** em todas as queries
- **`select_for_update`** ao fechar período (lock otimista)
- **Índices únicos** em:
  - `(mes, ano)` para PeriodoFinanceiro
  - `(contrato, periodo)` para ContratoSnapshot
- **JSONField** para detalhamento (evita tabelas adicionais)

---

## 🚀 COMO USAR

### 1. Migrar banco de dados
```bash
python manage.py makemigrations
python manage.py migrate
```

### 2. Criar superusuário (se não tiver)
```bash
python manage.py createsuperuser
```

### 3. Rodar servidor
```bash
python manage.py runserver
```

### 4. Acessar admin
```
http://localhost:8000/admin/
```

### 5. Criar dados de exemplo
1. Crie **Clientes**
2. Crie **Contratos** (com data_inicio e valor_mensal)
3. Crie **Domínios/VPS/Hostings** e vincule aos contratos
4. Crie **Custos** (DomainCost, VPSCost, etc) com:
   - valor_total
   - periodo_meses
   - data_inicio / data_fim / vencimento

### 6. Criar e fechar período
**Opção 1: Via Admin**
1. Vá em "Períodos Financeiros"
2. Adicione novo período (ex: 01/2026)
3. Clique em "Fechar Período"

**Opção 2: Via CLI**
```bash
python manage.py criar_periodo --mes 1 --ano 2026
python manage.py fechar_periodo --mes 1 --ano 2026
```

**Opção 3: Via Celery (automático)**
- Tasks rodam automaticamente conforme schedule

### 7. Ver dashboard
```
http://localhost:8000/financeiro/dashboard/
```

---

## 📋 REGRAS DE NEGÓCIO

### ✅ Contratos Ativos
Um contrato está ativo no período se:
- `data_inicio <= primeiro_dia_periodo`
- E `data_fim` é `null` OU `data_fim >= primeiro_dia_periodo`

### ✅ Custos Ativos
Um custo (DomainCost, VPSCost, etc) está ativo se:
- `data_inicio <= primeiro_dia_periodo`
- E `data_fim` é `null` OU `data_fim >= primeiro_dia_periodo`
- E `ativo = True`

### ✅ Rateio
- Custos são divididos **igualmente** entre contratos vinculados
- Exemplo: Domínio R$ 100/mês com 2 contratos = R$ 50 cada

### ✅ VPS e Backups
- VPS usa `VPSContrato` (M2M customizado com período)
- Backup segue a VPS (rateio igual aos contratos da VPS)

### ✅ Emails
- Email é custo direto do contrato específico (SEM rateio)
- Cada email pertence a um único contrato/cliente

---

## ⚠️ VALIDAÇÕES IMPORTANTES

### ❌ NÃO PERMITIDO:
1. **Fechar período já fechado**
2. **Alterar dados de período fechado**
3. **Excluir snapshots** (histórico imutável)
4. **Alterar custos** com períodos fechados posteriores
   - Solução: Criar novo custo com `data_inicio` futura
5. **Gerar snapshots duplicados** (constraint único)

### ✅ PERMITIDO:
1. Criar novos custos a qualquer momento
2. Marcar custos antigos como `ativo=False`
3. Adicionar observações em períodos

---

## 🔥 MELHORIAS FUTURAS

### Curto Prazo
- [ ] Enviar notificações em `task_alertar_vencimentos`
- [ ] Gráficos no dashboard (Chart.js ou similar)
- [ ] Filtros avançados no dashboard (por cliente, período)

### Médio Prazo
- [ ] API REST (Django REST Framework) para integração
- [ ] Previsão de custos futuros (ML)


## 🛡️ SEGURANÇA E BOAS PRÁTICAS

### ✅ O que está implementado:
- **Transaction.atomic()** em operações críticas
- **Select for update** para evitar race conditions
- **Validações em signals** (pré-save, pré-delete)
- **Constraints únicos** no banco
- **Readonly fields** onde necessário
- **Staff_member_required** no dashboard

### ⚠️ Pontos de Atenção:
- **Backup do banco** antes de fechar períodos importantes
- **Logs de auditoria** devem ser implementados
- **Permissões granulares** (considere django-guardian)
- **Testes automatizados** ainda não criados

---

## 🧪 TESTES RECOMENDADOS

```python
# TODO: Implementar testes
# tests/test_fechamento.py
# - Testar fechamento com contratos ativos/inativos
# - Testar rateio proporcional
# - Testar validações de período fechado
# - Testar proteção de custos históricos
# - Testar idempotência das tasks

# tests/test_rateio.py
# - Testar cálculo de custo mensal
# - Testar rateio com 1/N contratos
# - Testar casos extremos (custo zero, sem contratos)

# tests/test_signals.py
# - Testar proteção de snapshots
# - Testar proteção de período fechado
# - Testar proteção de custos históricos
```

---

## 🚫 ANTI-PATTERNS A EVITAR

### ❌ NÃO FAÇA:
1. **Lógica de negócio em models** → Use services
2. **Calcular custos em templates** → Use properties ou métodos do admin
3. **Alterar snapshots manualmente** → São imutáveis
4. **Executar fechamento sem transaction** → Use sempre atomic()
5. **Ignorar datas de vigência** → Sempre validar período
6. **Criar snapshots duplicados** → Constraint único previne

### ✅ FAÇA:
1. **Services para lógica complexa**
2. **Signals para validações automáticas**
3. **Management commands para operações CLI**
4. **Tasks do Celery para automação**
5. **Testes para regras críticas**

---

## 📞 SUPORTE

Em caso de dúvidas:
1. Verifique este README
2. Analise os comentários no código
3. Execute `python manage.py help <comando>`
4. Veja logs do Celery para tarefas assíncronas

---

## ✨ STATUS DO PROJETO

### ✅ PRONTO PARA PRODUÇÃO:
- Models e relacionamentos
- Services de fechamento e rateio
- Celery tasks e schedules
- Django Admin customizado
- Validações e signals
- Dashboard básico

### ⚠️ REVISAR ANTES DE PRODUÇÃO:
- Adicionar testes automatizados
- Configurar monitoring (Sentry, NewRelic)
- Configurar logs centralizados
- Implementar backup automatizado
- Revisar permissões de usuários
- Adicionar auditoria completa

### 🔜 BACKLOG:
- Sistema de notificações por email
- Relatórios PDF/Excel
- API REST
- Gráficos interativos

---

**Desenvolvido com ❤️ seguindo boas práticas de Django e arquitetura financeira**
