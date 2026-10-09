# Documentacao Geral - Control

## Visao geral
Aplicacao Django para cobranca mensal de clientes, integracao com InfinitePay, fila de mensagens (WAHA) e fechamento financeiro por contrato.

Objetivo principal:
- 1 invoice mensal por cliente
- valor total = soma dos contratos ativos
- receita por contrato via InvoiceContrato
- fechamento financeiro calcula lucro por contrato

## Telas (app `painel`, raiz do site, login de staff em /login/)
- Início: recebido/a receber/vencido do mês, atrasadas, próximos 15 dias, saúde (links, telefones, fila), últimos 6 meses.
- Cobranças (?mes=AAAA-MM): faturas do mês com ações (Recebi com data, lembrar no WhatsApp,
  refazer link, cancelar), contratos ainda sem mensalidade (Gerar agora), em aberto de outros meses.
- Clientes / ficha: contratos com valor vigente, reajustes, encerrar (desvincula recursos), faturas, recursos, margem.
- Agenda: faturas, renovações, reajustes e fim de contrato num lugar só; "Renovei" avança o vencimento.
- Recursos: infra com custo/mês, quem paga, renovação; ficha com histórico de custos e contratos vinculados.
- Financeiro: períodos, detalhe por contrato, despesas extras, fechar mês.
- O admin do Django continua em /admin/ como reserva.

## Modelos principais
- Cliente: dados do cliente e `vencimento_padrao` (1-28).
- Contrato: contrato mensal com `valor_mensal`, `data_inicio`, `data_fim`.
- Invoice: cobranca mensal do cliente.
- InvoiceContrato: vinculo invoice x contrato (receita por contrato).
- MessageQueue: fila de mensagens de cobranca e confirmacao.
- PeriodoFinanceiro / ContratoSnapshot: controle e fechamento financeiro por contrato.
- ContratoReajuste: valor do contrato a partir de um mês.
- Recurso / CustoRecurso / RecursoContrato (`infra.recursos`): toda a infra (domínio, VPS, hosting,
  backup, e-mail, outro). Vínculo com contrato tem datas; recurso sem vínculo próprio (backup) segue o `pai`.
  Os apps `infra.dominios/hosting/vps/backups/emails` são legado: dados copiados na migração
  `recursos.0002`, fora do admin e do código. Remover numa versão futura (drop das tabelas).

## Regras de faturamento
- Mensalidade (`Invoice.tipo='mensal'`): 1 fatura por cliente agrupando os contratos do mes.
- Contrato entra no mes se comecou ate o dia 1 (inicio no meio do mes: cobra a partir do seguinte).
- Cliente inativo nao e cobrado.
- Valor do contrato no mes = ultimo `ContratoReajuste` vigente, senao `valor_mensal` (escalonamento/reajuste).
- Vencimento baseado em `cliente.vencimento_padrao` (limite 1-28).
- Idempotente por contrato: o job roda todo dia e so fatura contrato ainda sem mensalidade no mes
  (cancelada conta como faturada, para nao voltar).
- Fatura avulsa (`tipo='avulsa'`, criada no admin) nao bloqueia a mensalidade.
- No admin o valor da fatura e a soma dos contratos vinculados; se mudar com a fatura em aberto, o checkout e refeito.
- Pagamento manual: status "Pago" no admin (ou acao "Marcar como pago") preenche `pago_em`, limpa cobrancas e envia confirmacao.
- Link curto `/p/<ref>/`: fatura paga leva ao recibo, cancelada mostra aviso (link antigo nao cobra mais).

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
- O webhook nao e assinado. Da baixa direto (como sempre) e depois confere na API
  (`payment_check`, `INFINITEPAY_PAYMENT_CHECK_URL` opcional): se a InfinitePay nao confirmar,
  nao responder ou o valor vier menor, avisa no Telegram. Nao bloqueia a baixa.
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
| gerar-invoices-mes-atual | `python manage.py run_job gerar_invoices_mes_atual` | `10 0 * * *` (diario) |
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

## Fila de mensagens: regras de envio
- Ate 10 por execucao, confirmacoes primeiro. Texto montado na hora do envio.
- Lembrete de 5/2 dias que perdeu a hora (fatura ja vencida) e descartado.
- Atraso: a cada 3 dias ate 30 dias; depois so voce acompanha. Fatura que vence vira aviso no Telegram.

## Datas monitoradas (resumo diario no Telegram, `alertar_vencimentos`)
- Infra: 30/15/7/3/1/0 dias antes; vencido e nao renovado, a cada 3 dias.
  Renovou? acao "Renovar" no admin do custo avanca o vencimento em `periodo_meses`.
- `pago_pelo_cliente`: custo que o cliente paga direto; so controla vencimento, fora de custo/margem.
- Contratos terminando e reajustes entrando em vigor: 30/7/0 dias.

## Fechamento financeiro por contrato
- Receita por contrato vem de `InvoiceContrato` (competencia; faturas canceladas ficam fora).
- Custo usado em periodo fechado nao muda valor; para trocar, encerrar (`data_fim`) e criar outro.
- Custos de `CustoRecurso` (exceto `pago_pelo_cliente`) divididos igualmente entre os contratos
  vinculados no mês (infra/financeiro/services).
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
