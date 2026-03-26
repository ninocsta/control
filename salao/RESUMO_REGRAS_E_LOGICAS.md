# Resumo Técnico do App `salao`

## 1) Objetivo Atual
O app `salao` é um módulo de gestão operacional/financeira para salão com:
- Lançamentos de atendimentos (receita líquida já descontando taxa de pagamento)
- Despesas (com suporte a parcelamento)
- Controle de produtos e estoque
- Compras de produtos vinculadas à despesa
- Saída de estoque para venda ou uso em cliente
- Dashboard mensal com KPIs de serviços e bloco separado de produtos

Hoje ele funciona como módulo interno, com acesso restrito a **superusuário**.

---

## 2) Arquitetura Atual
- Stack: Django + Templates server-side + JS inline para UX rápida
- Rotas: `salao/urls.py`
- Regras de negócio concentradas em: `salao/views.py`
- Persistência: `salao/models.py`
- Cobertura de regressão: `salao/tests.py`

### Rotas principais
- `/salao/dashboard/`
- `/salao/lancamentos/`
- `/salao/despesas/`
- `/salao/produtos/`
- `/salao/estoque/`
- `/salao/servicos/`
- `/salao/categorias/`
- `/salao/pagamentos/`

---

## 3) Controle de Acesso
Todas as views usam o decorator `_salao_superuser_required`, que exige:
- usuário autenticado
- `is_superuser = True`

Sem isso, redireciona para `/admin/login/`.

---

## 4) Modelos e Relacionamentos

## `ServicoSalao`
- `codigo` (único), `nome`, `valor_padrao`, `ativo`
- usado em `LancamentoSalao`

## `FormaPagamentoSalao`
- `codigo` (único), `nome`, `ativo`, `aceita_parcelamento`
- usado em `LancamentoSalao` e `MovimentoEstoqueSalao` (vendas)
- possui várias `TaxaFormaPagamentoSalao`

## `TaxaFormaPagamentoSalao`
- `forma_pagamento`, `parcelas (1..12)`, `percentual (0..100)`
- unique: `(forma_pagamento, parcelas)`

## `LancamentoSalao`
- `data`, `servico`, `forma_pagamento`, `parcelas`
- `valor_bruto`, `taxa_percentual_aplicada`, `valor_taxa`, `valor_cobrado`
- representa atendimento (não produto)

## `CategoriaDespesaSalao`
- `nome` (único), `ativo`
- pode ser usada como categoria geral e também como fornecedor (ex.: RIGOLIM, TOUT LISSE)

## `ProdutoSalao`
- `codigo` (único), `nome`, `unidade`, `ativo`
- `valor_venda_padrao`
- `estoque_minimo`
- `saldo_atual`
- `custo_medio_atual`

## `CompraEstoqueSalao`
- cabeçalho de compra de estoque
- `data`, `categoria_fornecedor`, `valor_total`, `parcelas_total`
- `grupo_parcelamento_id`, `observacao`

## `CompraEstoqueItemSalao`
- itens da compra de estoque
- `compra`, `produto`, `quantidade`, `custo_unitario`, `custo_total`

## `DespesaSalao`
- `data`, `categoria`, `valor`, `observacao`
- parcelamento: `grupo_parcelamento_id`, `parcela_numero`, `parcelas_total`
- `gera_estoque` (novo)
- `compra_estoque` (FK opcional)

## `MovimentoEstoqueSalao`
- `tipo`: `ENTRADA` / `SAIDA`
- `motivo`: `COMPRA`, `VENDA`, `USO_EM_CLIENTE`, `AJUSTE`
- `produto`, `data`, `quantidade`
- custo: `custo_unitario_aplicado`, `valor_custo_total`
- venda: `valor_venda_unitario`, `valor_bruto_venda`, `taxa_percentual_aplicada`, `valor_taxa`, `valor_liquido_venda`
- resultado: `lucro_produto`
- `forma_pagamento`, `parcelas`, `compra_estoque`, `observacao`

## `ComissaoMensalSalao`
- `ano`, `mes`, `percentual`
- `valor_pago_override` (mantido)
- `meta_faturamento`
- unique: `(ano, mes)`

---

## 5) Regras de Negócio Principais

## 5.1 Lançamentos de Atendimento (Receita de Serviços)
Fluxo `create_lancamento`:
1. Valida competência (`ano/mes/dia`)
2. Busca serviço ativo por `codigo`
3. Busca forma de pagamento ativa por `codigo_forma_pagamento`
4. Determina parcelas (forma sem parcelamento força `1`)
5. Exige taxa cadastrada para `(forma, parcelas)`
6. Calcula `valor_taxa` e `valor_liquido`
7. Salva lançamento com bruto, taxa e líquido

Regras importantes:
- Sem taxa cadastrada em atendimento, o lançamento é bloqueado.
- `valor_cobrado` representa o valor líquido do atendimento.

## 5.2 Despesas e Compra com Entrada em Estoque
Fluxo `create_despesa`:
1. Valida data, categoria e parcelas
2. Se `gera_estoque = False`:
- usa `valor` informado e segue fluxo tradicional de despesas parceladas
3. Se `gera_estoque = True`:
- exige itens (`produto`, `quantidade`, `custo_unitario`)
- calcula `valor_total` pela soma dos itens
- cria `CompraEstoqueSalao` + `CompraEstoqueItemSalao`
- registra movimentos de entrada (`motivo=COMPRA`)
- atualiza `saldo_atual` e `custo_medio_atual`
- gera despesas financeiras parceladas vinculadas à compra

Regras importantes:
- Entrada física do estoque ocorre na data da compra (integral).
- Financeiro continua parcelado por competência (como despesas normais).
- Edição direta de despesa com estoque é bloqueada para preservar consistência.
- Exclusão de compra com estoque reverte os movimentos vinculados e recompõe saldo/custo médio.

## 5.3 Saída de Estoque
Fluxo `create_saida_estoque` na tela de estoque:
1. Valida data, produto ativo, tipo de saída e quantidade
2. Bloqueia saída se `quantidade > saldo_atual`
3. Calcula custo da saída usando `custo_medio_atual`
4. Para `USO_EM_CLIENTE`:
- baixa estoque sem receita de venda
5. Para `VENDA`:
- exige forma de pagamento
- aplica regra de parcelas da forma
- busca taxa por `(forma, parcelas)`
- se não encontrar taxa, aplica `0%`
- calcula bruto, taxa, líquido e lucro da venda
6. Persiste `MovimentoEstoqueSalao` e atualiza saldo do produto

Regras importantes:
- Venda de produto **não entra na comissão de 20%** de atendimento.
- Bloqueio de estoque negativo é obrigatório.

## 5.4 Dashboard
Para competência `ano/mes`:

### Bloco de Serviços (já existente)
- `faturamento_liquido`, `faturamento_bruto_cliente`, `taxas_total`
- `despesas_total`
- comissão e lucro de serviços

### Bloco de Produtos (novo, separado)
- `vendas_produto_brutas`
- `taxas_produto_total`
- `vendas_produto_liquidas`
- `custo_produto_vendido`
- `lucro_produto`

### Alertas de Estoque
- lista produtos ativos com `saldo_atual <= estoque_minimo`
- exibida no dashboard e na tela de estoque

---

## 6) Comportamento de Interface (Templates/JS)

## Base
- navegação por abas
- toasts customizados com fila em `sessionStorage`

## Lançamentos
- fluxo rápido por código
- prévia instantânea de taxa e líquido
- refresh parcial (`?refresh=1`) com resumo + linhas do dia

## Despesas
- fluxo tradicional mantido
- opção `Compra com entrada em estoque`
- lançamento de múltiplos itens de produto quando aplicável

## Produtos
- CRUD completo de produtos
- parametrização de venda padrão e estoque mínimo

## Estoque
- saída por `VENDA` ou `USO_EM_CLIENTE`
- cálculo de venda líquida e lucro no ato da venda
- resumo mensal de vendas de produto
- tabela de saldos e alerta de reposição

## Dashboard
- KPIs e gráficos de serviços mantidos
- bloco financeiro de produtos separado
- alerta de estoque mínimo

---

## 7) Cobertura de Testes Atual (`salao/tests.py`)
Coberto:
- regras existentes de lançamentos, despesas, pagamentos, dashboard e cadastros
- despesas com `gera_estoque=False` sem movimentação de estoque
- compra com `gera_estoque=True` criando compra, itens, movimentos e custo médio
- compra parcelada com entrada física única
- saída de venda com taxa cadastrada
- saída de venda sem taxa cadastrada (`0%`)
- saída de uso em cliente
- bloqueio de estoque insuficiente
- dashboard separado para produto e sem comissão de 20% em vendas de produto
- alertas de estoque mínimo em estoque/dashboard

---

## 8) Limitações Estruturais Atuais
- Single-tenant
- Sem papéis por equipe (apenas superuser)
- Sem vínculo de estoque com profissional/cliente
- Sem agenda/calendário
- Sem controle de lote/validade por produto
- Sem inventário cíclico automatizado

---

## 9) Resumo Executivo
O `salao` evoluiu para um núcleo operacional mais completo:
- receitas de atendimento com taxa líquida
- despesas parceladas com possibilidade de compra de estoque por itens
- estoque com entrada, saída, custo médio e lucro por venda
- dashboard com visão separada de serviços e produtos
- alertas de reposição por estoque mínimo

A base está sólida para próximas evoluções (ex.: profissional, ajuste de inventário, integração com agenda), mantendo a simplicidade operacional atual.
