# Documentacao Geral - Control

## Visao geral
Aplicacao Django para cobranca mensal de clientes, integracao com InfinitePay, fila de mensagens (WAHA) e fechamento financeiro por contrato.

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
- Endpoint: `POST https://api.checkout.infinitepay.io/links`.
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

## Jobs periódicos (Scheduled Tasks do Coolify)
Sem Celery/Redis: cada job é uma função em `invoices/tasks.py` ou
`infra/financeiro/tasks.py`, rodada por `python manage.py run_job <nome>`.
No Coolify: recurso > Scheduled Tasks > Add, container `web`, cron abaixo.
O cron do Coolify segue o timezone do servidor (Servers > <servidor> > General >
Timezone): deixar `America/Sao_Paulo`, senão converter os horários para UTC (+3h).

| Nome | Comando | Cron (America/Sao_Paulo) |
|---|---|---|
| gerar-periodo-mes-atual | `python manage.py run_job gerar_periodo_mes_atual` | `5 0 1 * *` |
| gerar-invoices-mes-atual | `python manage.py run_job gerar_invoices_mes_atual` | `10 0 1 * *` |
| fechar-periodo-mes-anterior | `python manage.py run_job fechar_periodo_mes_anterior` | `0 2 1 * *` |
| gerar-checkouts-infinitepay | `python manage.py run_job processar_checkouts_infinitepay` | `40 7,15 * * *` |
| alertar-vencimentos | `python manage.py run_job alertar_vencimentos` | `0 8 * * *` |
| marcar-invoices-atrasados | `python manage.py run_job marcar_invoices_atrasados` | `0 9 * * *` |
| agendar-mensagens-cobranca | `python manage.py run_job agendar_mensagens_cobranca` | `10 9 * * *` |
| agendar-mensagens-atraso | `python manage.py run_job agendar_mensagens_atraso` | `20 9 * * *` |
| processar-fila-waha | `python manage.py run_job processar_fila_waha` | `0 9,11,13,15,17 * * 1-5` |

A confirmação de pagamento (`task_enviar_confirmacao_imediata`) sai na própria
requisição do webhook da InfinitePay, depois do commit; se o WAHA falhar, a
mensagem fica `pendente` e o `processar_fila_waha` reenvia.

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
