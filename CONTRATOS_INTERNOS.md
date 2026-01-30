# 🏢 Contratos Internos - Documentação

## 📋 Visão Geral

Este documento explica como o sistema trata **contratos internos** - contratos sem receita usados para controlar custos operacionais próprios da empresa.

## 🎯 Objetivo

Permitir que você controle seus próprios custos mensais (domínios, VPS, emails, etc.) dentro de um contrato especial, sem gerar receita, apenas rastreando despesas.

## 🔧 Como Funciona

### 1️⃣ **Cliente Interno**

Um cliente pode ser marcado como tipo **"Interno"** no cadastro:

```python
Cliente:
  - tipo = 'interno'  # Tipo especial para controle interno
  - nome = "Nicolas"  # Seu nome ou nome da empresa
```

### 2️⃣ **Contrato Interno**

Contratos de clientes internos têm características especiais:

- **Valor mensal = R$ 0,00** (sem receita)
- Usado apenas para rastrear custos
- Margem percentual = **NULL** (não faz sentido calcular sem receita)

```python
Contrato:
  - cliente = Cliente(tipo='interno')
  - valor_mensal = Decimal('0.00')  # Permitido para contratos internos
  - nome = "Nicolas"  # Nome do contrato
```

### 3️⃣ **Snapshot Financeiro**

Quando um período é fechado, o snapshot do contrato interno é criado assim:

```python
ContratoSnapshot:
  - receita = 0.00  # Sem receita
  - custo_total = 11.75  # Soma de todos os custos
  - margem = -11.75  # Sempre negativo (custo sem receita)
  - margem_percentual = NULL  # Interno não tem margem %
```

### 4️⃣ **Exibição no Dashboard e Admin**

- Dashboard: Margem % exibida como **"Interno"** (roxo)
- Admin: Lista de snapshots mostra **"Interno"** ao invés de porcentagem
- Cálculos globais consideram contratos internos corretamente

## 📊 Exemplo Prático

### Cenário:
Você tem um contrato interno "Nicolas" com os seguintes custos em Dezembro/2025:

- Domínios: R$ 2,17
- VPS: R$ 6,63
- Emails: R$ 2,95
- **Total: R$ 11,75**

### Resultado no Snapshot:
```
Contrato: Nicolas
Cliente: Nicolas (interno)
Período: 12/2025
Receita: R$ 0,00
Custo Total: R$ 11,75
Margem: -R$ 11,75
Margem %: Interno
```

## ✅ Validações

### Ao criar/editar contrato:

1. **Clientes NÃO internos**: `valor_mensal` deve ser > 0
2. **Clientes internos**: `valor_mensal` pode ser 0
3. Validação feita no método `clean()` do modelo `Contrato`

### Ao fechar período:

1. Verifica se cliente é interno: `contrato.cliente.tipo == 'interno'`
2. Se interno ou receita = 0:
   - `margem_percentual = NULL`
3. Se normal:
   - Calcula margem % com limite de ±99.999,99%

## 🗂️ Arquivos Modificados

### Models:
- [`contratos/models.py`](contratos/models.py) - Validação de valor_mensal
- [`infra/financeiro/models.py`](infra/financeiro/models.py) - margem_percentual null=True

### Services:
- [`infra/financeiro/services/fechamento_periodo.py`](infra/financeiro/services/fechamento_periodo.py) - Lógica de cálculo
- [`infra/financeiro/services/dashboard_service.py`](infra/financeiro/services/dashboard_service.py) - Tratamento de NULL

### Admin:
- [`infra/financeiro/admin.py`](infra/financeiro/admin.py) - Display "Interno"

### Templates:
- [`infra/financeiro/templates/admin/financeiro/dashboard.html`](infra/financeiro/templates/admin/financeiro/dashboard.html) - Filtro customizado
- [`infra/financeiro/templatetags/financeiro_tags.py`](infra/financeiro/templatetags/financeiro_tags.py) - Filtro `margem_format`

### Migrações:
- `contratos/migrations/0002_alter_contrato_valor_mensal.py`
- `infra/financeiro/migrations/0002_alter_contratosnapshot_margem_percentual.py`

## 🚀 Como Usar

### 1. Criar Cliente Interno

No admin Django:
1. Ir em **Clientes** → **Adicionar Cliente**
2. Preencher:
   - Nome: "Nicolas" (ou nome da empresa)
   - Email: seu email
   - Tipo: **Interno**
3. Salvar

### 2. Criar Contrato Interno

No admin Django:
1. Ir em **Contratos** → **Adicionar Contrato**
2. Preencher:
   - Cliente: Selecionar o cliente interno criado
   - Nome: "Nicolas" (ou nome identificador)
   - Valor mensal: **R$ 0,00**
   - Data início: Data atual
3. Salvar

### 3. Vincular Infraestrutura

Vincule seus recursos ao contrato interno:
- **Domínios**: Adicione o contrato em "Contratos" do domínio
- **VPS**: Crie VPSContrato vinculando ao contrato interno
- **Emails**: Vincule diretamente ao contrato
- **Hostings**: Adicione o contrato em "Contratos" do hosting

### 4. Fechar Período

Quando fechar o período:
1. Sistema detecta automaticamente que é contrato interno
2. Calcula custos normalmente
3. Define `margem_percentual = NULL`
4. Exibe como "Interno" no dashboard

## 📈 Dashboard

No dashboard financeiro, contratos internos são exibidos:

- **Card Margem %**: Exibe "Interno" em roxo
- **Análise de Contratos**: Mostra evolução de custos
- **Custos por Cliente**: Indica "Interno" na margem %

## ⚠️ Importante

- **Contratos internos não geram receita**
- **Margem sempre será negativa** (custos sem receita)
- **Útil para controle de gastos operacionais**
- **Não afeta cálculos de rentabilidade global** (pode ser filtrado)

## 🔍 Consultas Úteis

### Listar todos os contratos internos:
```python
from contratos.models import Contrato

contratos_internos = Contrato.objects.filter(
    cliente__tipo='interno'
).select_related('cliente')
```

### Ver custos de contratos internos:
```python
from infra.financeiro.models import ContratoSnapshot

snapshots_internos = ContratoSnapshot.objects.filter(
    contrato__cliente__tipo='interno'
).select_related('contrato', 'periodo')

for snap in snapshots_internos:
    print(f"{snap.periodo}: R$ {snap.custo_total} em custos")
```

## 📝 Notas Técnicas

### Por que margem_percentual = NULL?

- Calcular margem % sem receita resulta em divisão por zero ou valores absurdos (-117.400%)
- NULL é semanticamente correto: "não aplicável"
- Permite filtrar facilmente: `WHERE margem_percentual IS NULL`

### Por que permitir valor_mensal = 0?

- Contratos internos não geram receita real
- Forçar R$ 0,01 distorce análises financeiras
- Zero é semanticamente correto para "sem receita"

### Limite de margem_percentual

Para contratos normais com valores extremos:
- Limite: ±99.999,99%
- Evita overflow no banco de dados
- SQLite converte valores maiores incorretamente

---

**Última atualização**: 29/01/2026
