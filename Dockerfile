FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    # gunicorn lê WEB_CONCURRENCY como --workers; sobrescreva pelo painel.
    WEB_CONCURRENCY=2

WORKDIR /app

# Sem compilador: todas as dependências vêm em wheel (psycopg2-binary inclusive).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Valores falsos só para o settings carregar no collectstatic; os reais vêm do painel.
RUN SECRET_KEY=build ALERT_EMAIL_RECIPIENT=x \
    EMAIL_HOST=x EMAIL_PORT=0 EMAIL_HOST_USER=x EMAIL_HOST_PASSWORD=x \
    python manage.py collectstatic --noinput

# /app/media existe na imagem para o volume nomeado nascer com dono `app`.
RUN useradd --uid 1000 --create-home app \
    && mkdir -p /app/media \
    && chown app /app/media
USER app

EXPOSE 8000

CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "120"]
