"""
Django settings pro aplikaci FVE Dashboard.
"""

from pathlib import Path

# Základní cesta k projektu
BASE_DIR = Path(__file__).resolve().parent.parent

# Bezpečnostní nastavení
SECRET_KEY = 'django-insecure-!952hz4p!#(i5hag!*y!$!sx2ac%kr@!o4)+%(uodh4&pahodx'
DEBUG = True

# Seznam povolených hostů
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'bijec.nti.tul.cz',
    '165.232.77.216',
]

# Nainstalované aplikace
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'api',
    'corsheaders',
]

# Middleware
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'api.auth.SimpleAuthMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Nastavení sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24 hodin
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# URL konfigurace
ROOT_URLCONF = 'core.urls'

# Šablony
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Databázová konfigurace
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'fve_db',
        'USER': 'postgres',
        'PASSWORD': 'heslo',
        'HOST': 'db',
        'PORT': '5432',
    }
}

# Validace hesel
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internacionalizace
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Europe/Prague'
USE_I18N = True
USE_TZ = True

# Statické soubory
STATIC_URL = 'static/'

# Výchozí typ primárních klíčů
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS nastavení
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://bijec.nti.tul.cz:3000",
    "http://bijec.nti.tul.cz",
    "http://165.232.77.216:3000",
    "http://165.232.77.216"
]
CORS_ALLOW_CREDENTIALS = True 

# Logování
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {module}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': '/app/logs/django.log',
            'formatter': 'verbose',
        }
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'api': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG', 
            'propagate': True,
        }
    }
}

# Omezení požadavků
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_VIEW = 'django.http.HttpResponseForbidden'

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Bezpečnostní nastavení
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True