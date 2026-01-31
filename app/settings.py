from pathlib import Path
import environ
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# django-environ
env = environ.Env(
    DEBUG=(bool, False)
)

# Ler arquivo .env
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')


# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'django_celery_beat',

    # Local apps
    'clientes',
    'contratos',
    'invoices',
    'infra.dominios',
    'infra.vps',
    'infra.hosting',
    'infra.backups',
    'infra.emails',
    'infra.financeiro'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": env.db(),
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True



STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")



DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email Configuration
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env.int('EMAIL_PORT')
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = env('EMAIL_HOST_USER')

# Alertas de Vencimento
ALERT_EMAIL_RECIPIENT = env('ALERT_EMAIL_RECIPIENT')

LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'

CSRF_TRUSTED_ORIGINS = [
    "https://control.costatech.dev",
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_NAME = "control_sessionid"
CSRF_COOKIE_NAME = "control_csrftoken"


CELERY_BROKER_URL = 'redis://localhost:6379/2'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/2'
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = 'America/Sao_Paulo'
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_RESULT_EXPIRES = 3600  # 1 hora (ajuste conforme necessidade)

JAZZMIN_SETTINGS = {
    # 📌 Branding
    "site_title": "Control Admin",
    "site_header": "Painel Administrativo",
    "site_brand": "Control",
    "site_icon": "fas fa-laptop-code",
    "welcome_sign": "Bem-vindo ao Painel!",
    "copyright": "© 2026 Minha Empresa",
    "show_sidebar": True,

    # 🔗 Links customizados no menu
    "custom_links": {
        "financeiro": [
            {
                "name": "📊 Dashboard Financeiro",
                "url": "/financeiro/dashboard/",
                "icon": "fas fa-chart-line",
                "permissions": ["auth.view_user"],
            },
        ]
    },
    
    # 📋 Ordem e ícones dos apps no menu
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "clientes.cliente": "fas fa-user-tie",
        "contratos.contrato": "fas fa-file-contract",
        "invoices.invoice": "fas fa-file-invoice-dollar",
        "dominios.dominio": "fas fa-globe",
        "dominios.domaincost": "fas fa-dollar-sign",
        "vps.vps": "fas fa-server",
        "hosting.hosting": "fas fa-cloud",
        "emails.domainemail": "fas fa-envelope",
        "financeiro.periodofinanceiro": "fas fa-calendar-alt",
        "financeiro.contratosnapshot": "fas fa-camera",
    },
    
    # 🏠 Botão de dashboard na topbar
    "topmenu_links": [
        {"name": "Início", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "📊 Dashboard", "url": "/financeiro/dashboard/", "permissions": ["auth.view_user"]},
        {"model": "auth.User"},
    ],

}
