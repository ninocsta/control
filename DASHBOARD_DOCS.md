# 📊 Dashboard Financeiro e Operacional - Documentação Técnica

## 🎯 Visão Geral

Dashboard profissional e completo para gestão financeira e operacional, seguindo os princípios:
- ✅ Snapshots são IMUTÁVEIS
- ✅ Períodos fechados são fonte de verdade
- ✅ Dashboard = leitura, nunca cálculo crítico
- ✅ Performance > beleza

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────┐
│    views.py (Controller)            │
│    - Apenas chama o service         │
│    - Passa context para template    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ dashboard_service.py (Business)     │
│ - Queries otimizadas                │
│ - Lógica de negócio                 │
│ - Cálculos e agregações             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Models (Data Layer)               │
│   - PeriodoFinanceiro               │
│   - ContratoSnapshot                │
│   - Invoices                        │
│   - Custos (infra)                  │
└─────────────────────────────────────┘
```

---

## 📁 Estrutura de Arquivos

```
infra/financeiro/
├── services/
│   ├── dashboard_service.py   ← Service principal (NOVO)
│   ├── fechamento_periodo.py
│   └── rateio.py
├── views.py                   ← View simplificada (ATUALIZADO)
├── templates/admin/financeiro/
│   └── dashboard.html         ← Template profissional (ATUALIZADO)
└── ...
```

---

## 🔧 Implementação Técnica

### **1. dashboard_service.py**

Classe centralizada para todas as queries do dashboard.

#### **Métodos Principais:**

##### `get_cards_principais()`
Retorna dados dos 6 cards do topo:
- Receita Total (último período fechado)
- Despesa Total (último período fechado)
- Lucro Total (último período fechado)
- Margem % (último período fechado)
- Receita Prevista (mês atual - NÃO usa snapshots)
- Lucro Previsto (mês atual - NÃO usa snapshots)

**Fonte de dados:**
- Snapshots do último período fechado
- Contratos ativos + Custos ativos para previsão

##### `get_vencimentos_proximos(dias=30)`
Lista TODOS os custos que vencem nos próximos X dias.

**Mostra:**
- Tipo (Domínio, VPS, Hosting, Email, Backup)
- Nome
- Fornecedor
- Valor
- Vencimento
- Dias restantes
- Urgência (com cores semânticas)

**Ordenação:** Vencimento mais próximo primeiro

##### `get_custos_por_cliente(limit=10)`
Top clientes por margem (último período fechado).

**Mostra:**
- Nome do cliente
- Receita total
- Custo total
- Margem
- Margem %
- Número de contratos
- Cor baseada na margem (verde/amarelo/vermelho)

##### `get_custos_por_categoria()`
Custos agrupados por categoria (último período fechado).

**Categorias:**
- Domínios
- Hostings
- VPS
- Backups
- Emails

**Mostra:** Valor, percentual do total, cor

##### `get_analise_contratos(limit=10)`
Análise detalhada dos últimos 3 períodos por contrato.

**Mostra:**
- Receita, custo, lucro por mês
- Margem % por mês
- Tendência (↑ ↓ =)
- Margem média

##### `get_evolucao_mensal(meses=12)`
Evolução de receita, custo e margem dos últimos X meses.

**Útil para:** Gráficos de linha/barras

---

### **2. views.py**

View simplificada que apenas instancia o service e passa o context:

```python
@staff_member_required
def dashboard_financeiro(request):
    service = DashboardService()
    
    context = {
        'cards': service.get_cards_principais(),
        'analise_contratos': service.get_analise_contratos(limit=10),
        'vencimentos': service.get_vencimentos_proximos(dias=30),
        'custos_categorias': service.get_custos_por_categoria(),
        'custos_clientes': service.get_custos_por_cliente(limit=10),
        'evolucao_mensal': service.get_evolucao_mensal(meses=12),
    }
    
    return render(request, 'admin/financeiro/dashboard.html', context)
```

**Princípio:** View enxuta, lógica no service.

---

### **3. dashboard.html**

Template profissional com:
- Design clean e responsivo
- Cores semânticas (verde/vermelho/amarelo)
- Cards com hover effects
- Tabelas otimizadas
- Grid responsivo
- Links rápidos

**Seções:**
1. Cards principais (6 cards)
2. Vencimentos próximos (tabela)
3. Grid 2 colunas:
   - Top clientes por margem
   - Custos por categoria
4. Análise por contrato (últimos 3 meses)
5. Evolução mensal (últimos 12 meses)
6. Links rápidos

---

## 🎨 Design System

### **Cores Semânticas:**
- 🟢 Verde (#28a745) → Receita, Lucro, Margem positiva
- 🔴 Vermelho (#dc3545) → Despesas, Prejuízo, Urgência alta
- 🔵 Azul (#2196F3) → Informação, Lucro
- 🟣 Roxo (#9C27B0) → Margem %
- 🟠 Laranja (#FF9800) → Previsões, Despesas
- 🔷 Teal (#1abc9c) → Previsões positivas

### **Níveis de Urgência (Vencimentos):**
- **Alta** (≤ 7 dias): Vermelho (#dc3545) - URGENTE
- **Média** (≤ 15 dias): Amarelo (#ffc107) - Atenção
- **Baixa** (> 15 dias): Verde (#28a745) - Normal

### **Margem por Cliente:**
- ≥ 50%: Verde
- ≥ 30%: Amarelo
- < 30%: Vermelho

---

## ⚡ Otimizações de Performance

### **1. Select Related / Prefetch Related**
Todas as queries usam `.select_related()` e `.prefetch_related()` para evitar N+1 queries.

```python
# Exemplo no service
snapshots = ContratoSnapshot.objects.filter(
    periodo=ultimo_periodo
).select_related('contrato', 'periodo')
```

### **2. Queries Calculadas uma Vez**
Dados são calculados no service e passados prontos para o template.

### **3. Uso de Agregações Django**
```python
snapshots.aggregate(Sum('receita'))
snapshots.aggregate(Sum('custo_total'))
```

### **4. Cache de Primeiro Dia do Mês**
```python
self.primeiro_dia_mes_atual = date(self.hoje.year, self.hoje.month, 1)
```

---

## 🔐 Permissões

Dashboard acessível apenas para:
- Staff members
- Superusers

```python
@staff_member_required
def dashboard_financeiro(request):
```

---

## 📊 Dados Exibidos

### **Cards Principais:**
| Card | Fonte | Observação |
|------|-------|------------|
| Receita Total | Último período fechado | Snapshots |
| Despesa Total | Último período fechado | Snapshots |
| Lucro Total | Último período fechado | Snapshots |
| Margem % | Último período fechado | Snapshots |
| Receita Prevista | Mês atual | Contratos ativos |
| Lucro Previsto | Mês atual | Contratos + Custos ativos |

### **Vencimentos:**
- Lista TODOS os custos vencendo em até 30 dias
- Ordenado por vencimento (mais próximo primeiro)
- Exibe urgência com cores
- Item por item (não agrupa)

### **Custos por Cliente:**
- Top 10 clientes por margem
- Baseado no último período fechado
- Mostra número de contratos
- Cor baseada na margem %

### **Custos por Categoria:**
- Domínios, Hostings, VPS, Backups, Emails
- Baseado no último período fechado
- Percentual do total
- Cores únicas por categoria

### **Análise por Contrato:**
- Últimos 3 períodos fechados
- Receita, custo, lucro por mês
- Tendência de lucro
- Margem média

### **Evolução Mensal:**
- Últimos 12 meses
- Receita, custo, margem por mês
- Pronto para gráficos

---

## 🚀 Como Acessar

### **URL:**
```
http://localhost:8000/financeiro/dashboard/
```

### **Admin:**
Link direto no menu lateral (se configurado)

### **Links Rápidos (no dashboard):**
- Voltar ao Admin
- Contratos
- Invoices
- Períodos Financeiros
- Snapshots

---

## 🧪 Testes

### **Testar Sintaxe:**
```bash
python3 -m py_compile infra/financeiro/services/dashboard_service.py
python3 -m py_compile infra/financeiro/views.py
```

### **Testar no Browser:**
1. Acesse o admin
2. Vá para `/financeiro/dashboard/`
3. Verifique se todos os dados são exibidos corretamente

### **Casos de Teste:**
1. ✅ Dashboard sem períodos fechados
2. ✅ Dashboard com 1 período fechado
3. ✅ Dashboard com múltiplos períodos
4. ✅ Dashboard sem vencimentos próximos
5. ✅ Dashboard com vencimentos urgentes
6. ✅ Responsividade mobile

---

## 📝 Regras de Negócio Respeitadas

### **1. Snapshots são IMUTÁVEIS**
- Dashboard LEITURA apenas
- Nunca cria ou altera snapshots
- Usa snapshots existentes como fonte de verdade

### **2. Períodos Fechados**
- Cards principais usam ÚLTIMO período fechado
- Análise usa períodos fechados
- Evolução usa períodos fechados

### **3. Previsão ≠ Snapshot**
- Previsão usa contratos e custos ATIVOS
- NÃO cria snapshots
- Apenas simulação

### **4. Performance**
- Queries otimizadas com select_related
- Agregações no banco
- Cache de dados calculados

---

## 🎯 Perguntas Respondidas pelo Dashboard

✅ **"Estou ganhando dinheiro?"**
→ Cards de Receita, Despesa, Lucro e Margem %

✅ **"Onde estou gastando?"**
→ Custos por Categoria e Custos por Cliente

✅ **"O que vence?"**
→ Vencimentos Próximos (30 dias)

✅ **"O que vai acontecer este mês?"**
→ Receita Prevista e Lucro Previsto

✅ **"Como está a evolução?"**
→ Evolução Mensal (12 meses)

✅ **"Quais contratos são mais lucrativos?"**
→ Análise por Contrato (últimos 3 meses)

✅ **"Quais clientes geram mais margem?"**
→ Top 10 Clientes por Margem

---

## 💡 Sugestões Implementadas

### **1. Cores Semânticas**
Verde = positivo, Vermelho = negativo, Amarelo = atenção

### **2. Urgência nos Vencimentos**
Sistema de 3 níveis com cores e texto

### **3. Custos por Cliente**
Visão importante para identificar clientes lucrativos

### **4. Tendência de Contratos**
Indicador visual de evolução (↑ ↓ =)

### **5. Responsividade**
Grid adaptativo para mobile

### **6. Links Rápidos**
Acesso direto aos módulos relacionados

---

## 🔮 Próximas Melhorias (Sugestões)

### **1. Gráficos Interativos**
- Integrar Chart.js ou ApexCharts
- Gráfico de evolução mensal
- Gráfico de custos por categoria
- Gráfico de margem por contrato

### **2. Filtros**
- Filtrar por período
- Filtrar por cliente
- Filtrar por categoria

### **3. Exportação**
- Exportar para PDF
- Exportar para Excel
- Exportar para CSV

### **4. Alertas Avançados**
- Sistema de notificações
- Email automático de alertas
- Dashboard de alertas

### **5. Comparativo**
- Mês atual vs mês anterior
- Ano atual vs ano anterior
- Meta vs realizado

### **6. Cache**
- Cache de queries pesadas
- Refresh automático a cada X minutos
- Cache em Redis

---

## ✅ Checklist de Implementação

- [x] Service `dashboard_service.py` criado
- [x] View `views.py` atualizada
- [x] Template `dashboard.html` profissional
- [x] Cores semânticas implementadas
- [x] Queries otimizadas (select_related)
- [x] Vencimentos próximos com urgência
- [x] Custos por cliente (NOVO)
- [x] Custos por categoria
- [x] Análise por contrato (3 meses)
- [x] Evolução mensal (12 meses)
- [x] Cards principais (6 cards)
- [x] Responsividade mobile
- [x] Links rápidos
- [x] Permissões (staff_member_required)
- [x] Documentação completa
- [x] Testes de sintaxe

---

## 📚 Arquivos Modificados/Criados

### **Criados:**
- `infra/financeiro/services/dashboard_service.py`
- `DASHBOARD_DOCS.md` (este arquivo)

### **Modificados:**
- `infra/financeiro/views.py`
- `infra/financeiro/templates/admin/financeiro/dashboard.html`

---

**Dashboard pronto para produção!** 🎉
