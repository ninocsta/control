# 💼 Sistema de Controle Financeiro

Sistema completo de gestão de custos de infraestrutura e fechamento financeiro mensal para empresas de serviços de TI.

## 🚀 Quick Start

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Rodar Redis
docker run -d -p 6379:6379 redis:alpine

# 3. Migrations
python manage.py migrate
python manage.py createsuperuser

# 4. Rodar (3 terminais)
python manage.py runserver              # Terminal 1
celery -A app worker --loglevel=info    # Terminal 2
celery -A app beat --loglevel=info      # Terminal 3
```

Acesse:
- Admin: http://localhost:8000/admin/
- Dashboard: http://localhost:8000/financeiro/dashboard/

---

## 📊 Funcionalidades

### ✅ Gestão de Clientes e Contratos
- Cadastro de clientes (PF/PJ/Interno)
- Contratos com valor mensal e período de vigência
- Histórico completo de receitas

### ✅ Controle de Infraestrutura
- **Domínios**: Registro e renovação
- **Hostings**: Hospedagem de sites
- **VPS**: Servidores virtuais
- **Backups**: Backups de VPS
- **Emails**: Serviços de email

### ✅ Fechamento Financeiro Mensal
- ⚙️ Automático via Celery Beat (dia 1 às 02:00)
- 🖱️ Manual via Django Admin (botão "Fechar Período")
- 💻 CLI: `python manage.py fechar_periodo --mes 1 --ano 2026`

### ✅ Rateio de Custos
- Cálculo automático de custo mensal
- Rateio proporcional entre contratos
- Suporte a custos anuais, semestrais, trimestrais
- Detalhamento em JSON

### ✅ Snapshots Imutáveis
- 1 snapshot por contrato por mês
- Histórico protegido contra alterações
- Receita, custos, margem e margem %

### ✅ Dashboard Executivo
- Receita, custo e margem consolidados
- Evolução mensal
- Top contratos lucrativos
- Custos por categoria

### ✅ Alertas Automáticos
- Vencimentos em 30/7/0 dias
- Execução diária às 08:00
- Logs detalhados

### ✅ Invoices/Cobranças Automáticas ⭐ **NOVO**
- Geração automática de invoices mensais (dia 1 do mês)
- Soma automática de contratos ativos por cliente
- Vencimento padrão: dia 5 do mês
- Status: pendente → pago → atrasado
- Marcação automática de invoices atrasados (diário)
- Management command: `python manage.py gerar_invoices`

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────┐
│        DJANGO ADMIN                 │
│  (Interface de Gestão)              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│         SERVICES                    │
│  (Lógica de Negócio)                │
│  • Fechamento                       │
│  • Rateio                           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│          MODELS                     │
│  • PeriodoFinanceiro                │
│  • ContratoSnapshot                 │
│  • InfraCostModel                   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│         CELERY BEAT                 │
│  (Automação)                        │
│  • Gerar período                    │
│  • Fechar período                   │
│  • Alertar vencimentos              │
└─────────────────────────────────────┘
```

---

## 📁 Estrutura do Projeto

```
control/
├── app/                    # Configuração Django
├── clientes/               # Gestão de clientes
├── contratos/              # Gestão de contratos
├── invoices/               # Faturamento (InfinitePay)
├── infra/
│   ├── core/               # Models abstratos
│   ├── dominios/           # Domínios
│   ├── hosting/            # Hospedagem
│   ├── vps/                # Servidores VPS
│   ├── backups/            # Backups
│   ├── emails/             # Serviços de email
│   └── financeiro/         # 💰 Fechamento financeiro
│       ├── services/       # Lógica de negócio
│       ├── management/     # Commands CLI
│       ├── templates/      # Dashboard
│       ├── tasks.py        # Celery tasks
│       └── signals.py      # Proteções
└── docs/                   # Documentação completa
```

---

## 📚 Documentação

| Arquivo | Descrição |
|---------|-----------|
| [TASKS_IMPLEMENTADAS.md](TASKS_IMPLEMENTADAS.md) | ⭐ Sistema de automação completo |
| [INDICE_DOCUMENTACAO.md](INDICE_DOCUMENTACAO.md) | 📚 Índice de toda documentação |
| [TASKS_QUICK_REF.md](TASKS_QUICK_REF.md) | ⚡ Referência rápida de tasks |
| [AUTOMACAO_COMPLETA.md](AUTOMACAO_COMPLETA.md) | 🤖 Detalhes de automação |
| [INVOICES_TASKS.md](INVOICES_TASKS.md) | 💰 Tasks de invoices |
| [QUICK_START.md](QUICK_START.md) | ⚡ Começar em 5 minutos |
| [RESUMO_TECNICO_1PG.md](RESUMO_TECNICO_1PG.md) | 📄 Resumo de 1 página |
| [RESUMO_EXECUTIVO.md](RESUMO_EXECUTIVO.md) | 📊 Visão completa |
| [FINANCEIRO_README.md](FINANCEIRO_README.md) | 📖 Guia detalhado |
| [ANALISE_TECNICA.md](ANALISE_TECNICA.md) | 🔍 Arquitetura profunda |
| [SUGESTOES_E_ANTIPATTERNS.md](SUGESTOES_E_ANTIPATTERNS.md) | ✅ Boas práticas |
| [SETUP_DEPLOYMENT.md](SETUP_DEPLOYMENT.md) | 🚀 Deploy produção |
| [ESTRUTURA_PROJETO.md](ESTRUTURA_PROJETO.md) | 📁 Arquivos do projeto |

---

## 🛠️ Tecnologias

- **Backend:** Django 5.2
- **Task Queue:** Celery 5.3+
- **Broker:** Redis
- **Database:** PostgreSQL (recomendado)
- **Scheduler:** Celery Beat
- **Admin:** Django Admin (customizado)

---

## ⚙️ Instalação Completa

### 1. Clonar repositório
```bash
git clone <repo-url>
cd control
```

### 2. Criar ambiente virtual
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Instalar dependências
```bash
pip install -r requirements.txt
```

### 4. Configurar .env
```env
DEBUG=True
SECRET_KEY=sua-chave-secreta
DATABASE_URL=postgres://user:pass@localhost/control_db
CELERY_BROKER_URL=redis://localhost:6379/2
```

### 5. Rodar migrations
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Iniciar serviços
```bash
# Terminal 1: Django
python manage.py runserver

# Terminal 2: Celery Worker
celery -A app worker --loglevel=info

# Terminal 3: Celery Beat
celery -A app beat --loglevel=info
```

---

## 📊 Uso Básico

### 1. Criar Cliente
```
Admin → Clientes → Adicionar
```

### 2. Criar Contrato
```
Admin → Contratos → Adicionar
- Vincular ao cliente
- Definir valor mensal
- Data início/fim
```

### 3. Criar Infraestrutura
```
Admin → Domínios/VPS/Hosting → Adicionar
- Vincular contratos
- Adicionar custos (inline)
```

### 4. Fechar Período
```
Admin → Períodos Financeiros → Fechar Período
```

### 5. Ver Dashboard
```
http://localhost:8000/financeiro/dashboard/
```

---

## 🔄 Fluxo de Fechamento

```
1. Celery cria período do mês atual (dia 1 às 00:05)
2. Celery fecha mês anterior (dia 1 às 02:00)
   ├─ Busca contratos ativos
   ├─ Busca custos ativos
   ├─ Calcula rateio proporcional
   ├─ Cria snapshots (1 por contrato)
   └─ Marca período como fechado
3. Snapshots ficam disponíveis no admin e dashboard
```

---

## 🧪 Testes

```bash
# Rodar testes (quando implementados)
python manage.py test

# Verificar Celery tasks
celery -A app inspect registered

# Testar fechamento manual
python manage.py fechar_periodo --mes 1 --ano 2026
```

---

## 🐳 Docker

```bash
# Rodar com Docker Compose
docker-compose up -d

# Migrations
docker-compose exec web python manage.py migrate

# Criar superuser
docker-compose exec web python manage.py createsuperuser
```

---

## 📈 Roadmap

### ✅ v1.0 (Atual)
- [x] Fechamento financeiro automático
- [x] Rateio de custos
- [x] Snapshots imutáveis
- [x] Dashboard básico
- [x] Celery tasks

### 🔜 v1.1 (Próximo)
- [ ] Testes automatizados
- [ ] Notificações por email
- [ ] Relatórios PDF/Excel
- [ ] Gráficos interativos

### 🔮 v2.0 (Futuro)
- [ ] API REST
- [ ] App mobile
- [ ] ML para previsões
- [ ] Multi-moeda

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

---

## 📝 Licença

Este projeto é proprietário. Todos os direitos reservados.

---

## 👨‍💻 Autor

Desenvolvido por [Seu Nome]

---

## 📞 Suporte

- 📧 Email: suporte@empresa.com
- 📚 Docs: [QUICK_START.md](QUICK_START.md)
- 🐛 Issues: GitHub Issues

---

**Sistema pronto para uso! 🚀**
