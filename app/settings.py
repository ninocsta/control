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

# Coolify: o valor precisa terminar com `,localhost` (healthcheck bate em localhost de dentro do container).
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])


# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Local apps
    'clientes',
    'contratos',
    'invoices',
    'salao',
    'infra.dominios',
    'infra.vps',
    'infra.hosting',
    'infra.backups',
    'infra.emails',
    'infra.financeiro'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
    # Sem DATABASE_URL (dev local) cai no SQLite.
    "default": env.db(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
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
MEDIA_ROOT = env("MEDIA_ROOT", default=os.path.join(BASE_DIR, "media"))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Manifest só fora do DEBUG: exige o collectstatic (feito no build da imagem).
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}



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

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["https://control.costatech.dev"])

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_NAME = "control_sessionid"
CSRF_COOKIE_NAME = "control_csrftoken"



JAZZMIN_SETTINGS = {
    # 📌 Branding
    "site_title": "Control Admin",
    "site_header": "Painel Administrativo",
    "site_brand": "Control",
    # Caminho de imagem em static (favicon), não classe de ícone: com o storage Manifest
    # a classe "fas fa-laptop-code" derrubava o admin com 500.
    "site_icon": None,
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
        {"name": "💇 Dashboard Salão", "url": "/salao/dashboard/", "permissions": ["auth.view_user"]},
    ],

}

# Logs no stdout (aparecem nos logs do container mesmo com DEBUG=False);
# django.request em ERROR inclui o traceback das exceções 500.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout", "formatter": "simple"},
        "telegram": {"class": "app.notify.TelegramErrorHandler", "level": "ERROR"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console", "telegram"], "level": "ERROR", "propagate": False},
    },
}
