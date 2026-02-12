# Documentacao Geral - Control

## Visao geral
Aplicacao Django com Celery para cobranca mensal de clientes, integracao com InfinitePay, fila de mensagens (WAHA) e fechamento financeiro por contrato.

Objetivo principal:
- 1 invoice mensal por cliente
- valor total = soma dos contratos ativos
- receita por contrato via InvoiceContrato
- fechamento financeiro calcula lucro por contrato

## Modelos principais
- Cliente: dados do cliente e `vencimento_padrao` (1-28).
- Contrato: contrato mensal com `valor_mensal`, `data_inicio`, `data_fim`.
- Invoice: cobranca mensal do cliente.
- InvoiceContrato: vinculo invoice x contrato (receita por contrato).
- MessageQueue: fila de mensagens de cobranca e confirmacao.
- PeriodoFinanceiro / ContratoSnapshot: controle e fechamento financeiro por contrato.

## Regras de faturamento
- 1 invoice por cliente por mes.
- Soma de todos os contratos ativos no mes.
- Vencimento baseado em `cliente.vencimento_padrao` (limite 1-28).
- Idempotente: nao cria invoice duplicado para cliente/mes quando ja existe invoice com vinculos.
- Invoices manuais sem vinculo nao bloqueiam a geracao automatica.

## Integracao InfinitePay
- Service: `invoices/services/infinitepay_service.py`.
- Endpoint: `POST https://api.infinitepay.io/invoices/public/checkout/links`.
- Payload:
  - `handle`
  - `items` (quantity=1, price em centavos, description generica)
  - `order_nsu` = `invoice.id`
  - `webhook_url`
  - `customer` (name, email, phone_number) quando existir
- Resposta esperada: `url` (checkout) e opcionalmente `invoice_slug`.
- Falha no checkout nao bloqueia criacao da invoice (retry via task).

## Webhook InfinitePay
- URL: `/webhooks/infinitepay/`
- Busca invoice por `invoice_slug` ou `order_nsu`.
- Marca como pago e salva `transaction_nsu`, `receipt_url`, `capture_method`.
- Agenda mensagem de confirmacao na fila.
- Responde rapido (logica leve).

## Fila de mensagens (WAHA)
- Modelo: `MessageQueue` com `tipo` (5_dias, 2_dias, no_dia, confirmacao).
- Constraint unica: `(invoice, tipo)` para evitar duplicidade.
- Mensagens:
  - 5 dias antes
  - 2 dias antes
  - no dia
  - confirmacao de pagamento

## Tasks (Celery)
- `task_gerar_invoices_mes_atual`: gera invoices mensais por cliente.
- `task_marcar_invoices_atrasados`: marca pendentes vencidas como atrasadas.
- `task_agendar_mensagens_cobranca`: agenda mensagens conforme vencimento.
- `task_processar_fila_waha`: envia mensagens pendentes via WAHA.
- `task_processar_checkouts_infinitepay`: retry de checkouts pendentes.

## Fechamento financeiro por contrato
- Receita por contrato vem de `InvoiceContrato`.
- Custos sao rateados no fechamento (infra/financeiro/services).
- Gera `ContratoSnapshot` com receita, custo e margem por contrato.

## Variaveis de ambiente principais
InfinitePay:
- `INFINITEPAY_HANDLE`
- `INFINITEPAY_WEBHOOK_URL`
- `INFINITEPAY_ITEM_DESCRIPTION`

WAHA:
- `WAHA_BASE_URL`
- `WAHA_API_KEY`
- `WAHA_SESSION`

## Observacoes
- Logica de negocio permanece fora dos models.
- Services concentram integracoes externas e calculos.
- Tasks pequenas e idempotentes.
