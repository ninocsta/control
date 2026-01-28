# ⚡ QUICK START - Sistema Financeiro

## 🚀 Começar em 5 minutos

### 1️⃣ Instalar dependências
```bash
pip install celery redis django-celery-beat
```

### 2️⃣ Rodar Redis
```bash
docker run -d -p 6379:6379 --name redis redis:alpine
```

### 3️⃣ Migrations
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 4️⃣ Rodar servidores (3 terminais)
```bash
# Terminal 1
python manage.py runserver

# Terminal 2
celery -A app worker --loglevel=info

# Terminal 3
celery -A app beat --loglevel=info
```

### 5️⃣ Acessar
- Admin: http://localhost:8000/admin/
- Dashboard: http://localhost:8000/financeiro/dashboard/

---

## 📝 Criar primeiro fechamento

### Passo 1: Criar dados básicos
1. Acesse `/admin/clientes/cliente/add/`
2. Crie um cliente (ex: "Empresa X")
3. Vá em `/admin/contratos/contrato/add/`
4. Crie um contrato:
   - Cliente: Empresa X
   - Valor mensal: R$ 1.000
   - Data início: 01/01/2026
   - Data fim: (deixe vazio)

### Passo 2: Criar infraestrutura
1. Vá em `/admin/dominios/dominio/add/`
2. Crie um domínio:
   - Nome: cliente.com.br
   - Fornecedor: Registro.br
   - Contratos: [Selecione o contrato criado]
   - Ativo: ✓

### Passo 3: Criar custo
1. Dentro do domínio, adicione um custo (inline):
   - Valor total: R$ 40,00
   - Período meses: 1
   - Data início: 01/01/2026
   - Data fim: (vazio)
   - Vencimento: 01/02/2026
   - Ativo: ✓

### Passo 4: Criar período
1. Vá em `/admin/financeiro/periodofinanceiro/add/`
2. Crie período:
   - Mês: 1
   - Ano: 2026
   - Salvar

### Passo 5: Fechar período
1. Na lista de períodos, clique em "🔒 Fechar Período"
2. Aguarde processamento
3. Veja snapshot criado!

### Passo 6: Ver resultados
1. Dashboard: `/financeiro/dashboard/`
2. Snapshot: `/admin/financeiro/contratosnapshot/`
3. Contrato: Veja inline de snapshots

---

## 🧪 Testar Celery

### Verificar tasks registradas:
```bash
celery -A app inspect registered
```

Deve aparecer:
- `infra.financeiro.tasks.task_gerar_periodo_mes_atual`
- `infra.financeiro.tasks.task_fechar_periodo_mes_anterior`
- `infra.financeiro.tasks.task_alertar_vencimentos`

### Executar task manualmente:
```python
# Shell Django
python manage.py shell

from infra.financeiro.tasks import task_gerar_periodo_mes_atual
task_gerar_periodo_mes_atual.delay()
```

### Ver schedule do Beat:
```bash
celery -A app inspect scheduled
```

---

## 📊 Ver Dashboard

Acesse: http://localhost:8000/financeiro/dashboard/

Você verá:
- ✅ Receita total
- ✅ Custo total
- ✅ Margem total
- ✅ Margem %
- ✅ Tabela por mês
- ✅ Top contratos
- ✅ Custos por categoria

---

## 🐛 Troubleshooting Rápido

### Redis não conecta?
```bash
# Verificar se Redis está rodando
redis-cli ping
# Deve retornar: PONG

# Se não estiver, rodar:
docker start redis
```

### Import error?
```bash
# Verificar INSTALLED_APPS em settings.py
'infra.financeiro',  # Deve estar assim (com infra.)
```

### Migrations error?
```bash
python manage.py migrate --fake-merge
```

### Celery não vê tasks?
```bash
# Reiniciar worker e beat
# Ctrl+C nos terminais 2 e 3
# Rodar novamente:
celery -A app worker --loglevel=info
celery -A app beat --loglevel=info
```

---

## 📚 Documentação Completa

- **FINANCEIRO_README.md** - Guia completo de uso
- **ANALISE_TECNICA.md** - Arquitetura e decisões
- **SUGESTOES_E_ANTIPATTERNS.md** - Boas práticas
- **SETUP_DEPLOYMENT.md** - Deploy em produção
- **RESUMO_EXECUTIVO.md** - Visão geral

---

## 🎯 Comandos Úteis

```bash
# Criar período
python manage.py criar_periodo --mes 1 --ano 2026

# Fechar período
python manage.py fechar_periodo --mes 1 --ano 2026

# Ver logs do Celery
tail -f celery.log

# Limpar tasks do Celery
celery -A app purge

# Ver tasks ativas
celery -A app inspect active
```

---

## ✅ Checklist de Sucesso

- [ ] Redis rodando (redis-cli ping → PONG)
- [ ] Migrations aplicadas
- [ ] Superusuário criado
- [ ] Servidor Django rodando
- [ ] Celery Worker rodando
- [ ] Celery Beat rodando
- [ ] Cliente criado
- [ ] Contrato criado
- [ ] Infraestrutura criada
- [ ] Custo criado
- [ ] Período criado
- [ ] Período fechado com sucesso
- [ ] Snapshot visível
- [ ] Dashboard acessível

---

**Se todos os itens acima estiverem ✅, o sistema está funcionando! 🎉**
