# 🚀 GUIA DE SETUP E DEPLOYMENT

## 📦 INSTALAÇÃO E CONFIGURAÇÃO

### 1. Instalar Dependências

Atualize o `requirements.txt`:
```txt
# Já existentes
Django>=5.2
django-environ
psycopg2-binary  # ou psycopg2
Pillow

# Novas dependências
celery>=5.3.0
redis>=4.5.0
django-celery-beat>=2.5.0
```

Instalar:
```bash
pip install -r requirements.txt
```

---

### 2. Configurar Redis

**Opção A: Docker (recomendado)**
```bash
docker run -d -p 6379:6379 --name redis redis:alpine
```

**Opção B: Instalação local**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# macOS
brew install redis
brew services start redis

# Windows
# Baixar de: https://github.com/microsoftarchive/redis/releases
```

**Verificar:**
```bash
redis-cli ping
# Deve retornar: PONG
```

---

### 3. Configurar Banco de Dados

Se ainda não tiver PostgreSQL configurado:

```bash
# Criar banco
sudo -u postgres psql
CREATE DATABASE control_db;
CREATE USER control_user WITH PASSWORD 'senha_segura';
GRANT ALL PRIVILEGES ON DATABASE control_db TO control_user;
\q
```

**.env:**
```env
DATABASE_URL=postgres://control_user:senha_segura@localhost/control_db
```

---

### 4. Migrations

```bash
# Gerar migrations
python manage.py makemigrations

# Aplicar migrations
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser
```

---

### 5. Rodar Celery Worker e Beat

**Terminal 1: Django Server**
```bash
python manage.py runserver
```

**Terminal 2: Celery Worker**
```bash
celery -A app worker --loglevel=info
```

**Terminal 3: Celery Beat (Agendador)**
```bash
celery -A app beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

### 6. Verificar Instalação

1. Acesse admin: `http://localhost:8000/admin/`
2. Crie um período: `Períodos Financeiros → Adicionar`
3. Verifique dashboard: `http://localhost:8000/financeiro/dashboard/`
4. Verifique tasks do Celery:
   ```bash
   celery -A app inspect active
   ```

---

## 🔧 TROUBLESHOOTING

### Problema: Celery não encontra tasks

**Sintoma:**
```
KeyError: 'infra.financeiro.tasks.task_gerar_periodo_mes_atual'
```

**Solução:**
1. Verificar `INSTALLED_APPS` em `settings.py`:
   ```python
   'infra.financeiro',  # Deve estar aqui
   ```

2. Verificar `apps.py`:
   ```python
   class FinanceiroConfig(AppConfig):
       name = 'infra.financeiro'  # Deve ser path completo
   ```

3. Reiniciar Celery Worker

---

### Problema: Redis connection refused

**Sintoma:**
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379
```

**Solução:**
```bash
# Verificar se Redis está rodando
redis-cli ping

# Se não estiver, iniciar
sudo systemctl start redis  # Linux
brew services start redis   # macOS
```

---

### Problema: Migrations conflitantes

**Sintoma:**
```
django.db.migrations.exceptions.InconsistentMigrationHistory
```

**Solução:**
```bash
# Opção 1: Fake merge
python manage.py migrate --fake-merge

# Opção 2: Reset (CUIDADO: apaga dados!)
python manage.py migrate infra.financeiro zero
python manage.py migrate
```

---

### Problema: Import error no core.models

**Sintoma:**
```
ModuleNotFoundError: No module named 'core'
```

**Solução:**
Os imports devem ser assim:
```python
# ❌ ERRADO
from core import models as core_models

# ✅ CORRETO
from infra.core import models as core_models
```

Se necessário, ajuste os imports nos arquivos:
- `infra/dominios/models.py`
- `infra/hosting/models.py`
- `infra/vps/models.py`
- `infra/backups/models.py`
- `infra/emails/models.py`

---

## 🐳 DEPLOYMENT COM DOCKER

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Dependências do sistema
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

# Collectstatic
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8000"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: control_db
      POSTGRES_USER: control_user
      POSTGRES_PASSWORD: senha_segura
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  web:
    build: .
    command: gunicorn app.wsgi:application --bind 0.0.0.0:8000
    volumes:
      - .:/app
      - static_volume:/app/static
      - media_volume:/app/media
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - db
      - redis

  celery_worker:
    build: .
    command: celery -A app worker --loglevel=info
    volumes:
      - .:/app
    env_file:
      - .env
    depends_on:
      - db
      - redis

  celery_beat:
    build: .
    command: celery -A app beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    volumes:
      - .:/app
    env_file:
      - .env
    depends_on:
      - db
      - redis

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - static_volume:/app/static
      - media_volume:/app/media
    depends_on:
      - web

volumes:
  postgres_data:
  static_volume:
  media_volume:
```

### nginx.conf

```nginx
events {
    worker_connections 1024;
}

http {
    upstream django {
        server web:8000;
    }

    server {
        listen 80;
        server_name localhost;

        location /static/ {
            alias /app/static/;
        }

        location /media/ {
            alias /app/media/;
        }

        location / {
            proxy_pass http://django;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### Comandos Docker

```bash
# Build e rodar
docker-compose up -d --build

# Migrations
docker-compose exec web python manage.py migrate

# Criar superuser
docker-compose exec web python manage.py createsuperuser

# Ver logs
docker-compose logs -f web
docker-compose logs -f celery_worker
docker-compose logs -f celery_beat

# Parar
docker-compose down

# Parar e remover volumes
docker-compose down -v
```

---

## 🌐 DEPLOYMENT EM PRODUÇÃO

### 1. Servidor (Ubuntu/Debian)

**Instalar dependências:**
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv nginx postgresql postgresql-contrib redis-server
```

**Criar usuário:**
```bash
sudo adduser control
sudo usermod -aG sudo control
su - control
```

**Clonar projeto:**
```bash
cd /home/control
git clone https://github.com/seu-usuario/control.git
cd control
```

**Ambiente virtual:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

**Configurar .env:**
```bash
cp .env.example .env
nano .env
```

```env
DEBUG=False
SECRET_KEY=gere_uma_chave_segura_aqui
ALLOWED_HOSTS=seu-dominio.com,www.seu-dominio.com
DATABASE_URL=postgres://control_user:senha@localhost/control_db
CELERY_BROKER_URL=redis://localhost:6379/2
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

**Migrations e static:**
```bash
python manage.py migrate
python manage.py collectstatic
```

---

### 2. Systemd Services

**Gunicorn: `/etc/systemd/system/control.service`**
```ini
[Unit]
Description=Control Django App
After=network.target

[Service]
User=control
Group=www-data
WorkingDirectory=/home/control/control
Environment="PATH=/home/control/control/venv/bin"
ExecStart=/home/control/control/venv/bin/gunicorn \
          --workers 3 \
          --bind unix:/home/control/control/control.sock \
          app.wsgi:application

[Install]
WantedBy=multi-user.target
```

**Celery Worker: `/etc/systemd/system/control-celery.service`**
```ini
[Unit]
Description=Control Celery Worker
After=network.target

[Service]
Type=forking
User=control
Group=www-data
WorkingDirectory=/home/control/control
Environment="PATH=/home/control/control/venv/bin"
ExecStart=/home/control/control/venv/bin/celery -A app worker \
          --loglevel=info \
          --logfile=/var/log/celery/worker.log \
          --pidfile=/var/run/celery/worker.pid

[Install]
WantedBy=multi-user.target
```

**Celery Beat: `/etc/systemd/system/control-celery-beat.service`**
```ini
[Unit]
Description=Control Celery Beat
After=network.target

[Service]
Type=forking
User=control
Group=www-data
WorkingDirectory=/home/control/control
Environment="PATH=/home/control/control/venv/bin"
ExecStart=/home/control/control/venv/bin/celery -A app beat \
          --loglevel=info \
          --logfile=/var/log/celery/beat.log \
          --pidfile=/var/run/celery/beat.pid \
          --scheduler django_celery_beat.schedulers:DatabaseScheduler

[Install]
WantedBy=multi-user.target
```

**Iniciar serviços:**
```bash
sudo systemctl daemon-reload
sudo systemctl start control
sudo systemctl start control-celery
sudo systemctl start control-celery-beat
sudo systemctl enable control
sudo systemctl enable control-celery
sudo systemctl enable control-celery-beat
```

---

### 3. Nginx

**`/etc/nginx/sites-available/control`**
```nginx
server {
    listen 80;
    server_name seu-dominio.com www.seu-dominio.com;

    location /static/ {
        alias /home/control/control/static/;
    }

    location /media/ {
        alias /home/control/control/media/;
    }

    location / {
        proxy_pass http://unix:/home/control/control/control.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Ativar:**
```bash
sudo ln -s /etc/nginx/sites-available/control /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

### 4. SSL com Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d seu-dominio.com -d www.seu-dominio.com
```

---

### 5. Firewall

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 📊 MONITORAMENTO

### Logs

```bash
# Django
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Celery
tail -f /var/log/celery/worker.log
tail -f /var/log/celery/beat.log

# Systemd
journalctl -u control -f
journalctl -u control-celery -f
```

---

### Sentry (Error Tracking)

**Instalar:**
```bash
pip install sentry-sdk
```

**settings.py:**
```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

if not DEBUG:
    sentry_sdk.init(
        dsn="seu-dsn-aqui",
        integrations=[DjangoIntegration()],
        traces_sample_rate=1.0,
    )
```

---

## 🔄 BACKUP E RESTORE

### Backup Diário (Cron)

**`/home/control/backup.sh`:**
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/control/backups"

# Backup banco
pg_dump control_db > $BACKUP_DIR/db_$DATE.sql

# Backup media
tar -czf $BACKUP_DIR/media_$DATE.tar.gz /home/control/control/media/

# Manter apenas últimos 7 dias
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

**Agendar:**
```bash
chmod +x /home/control/backup.sh
crontab -e
```

```cron
0 3 * * * /home/control/backup.sh
```

### Restore

```bash
# Restaurar banco
psql control_db < /home/control/backups/db_20260128_030000.sql

# Restaurar media
tar -xzf /home/control/backups/media_20260128_030000.tar.gz -C /
```

---

## ✅ CHECKLIST FINAL

- [ ] `.env` configurado corretamente
- [ ] `DEBUG = False` em produção
- [ ] PostgreSQL funcionando
- [ ] Redis funcionando
- [ ] Migrations aplicadas
- [ ] Superusuário criado
- [ ] Celery Worker rodando
- [ ] Celery Beat rodando
- [ ] Nginx configurado
- [ ] SSL instalado
- [ ] Firewall ativado
- [ ] Backup automatizado
- [ ] Logs configurados
- [ ] Sentry configurado (opcional)
- [ ] Testes rodando

---

**Sistema pronto para produção! 🚀**
