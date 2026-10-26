import os
import sys
import json
import logging
from pathlib import Path
from datetime import timedelta
import dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
dotenv.load_dotenv(BASE_DIR / '.env')

# Security: SECRET_KEY must come from environment in production.
_secret_key = os.environ.get('SECRET_KEY')
_debug_mode = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')
if not _secret_key and not _debug_mode:
    raise Exception(
        'SECURITY ERROR: SECRET_KEY environment variable is required in production. '
        'Generate one with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
    )
SECRET_KEY = _secret_key or 'django-insecure-dev-only-key-not-for-production'
DEBUG = _debug_mode

# Detect test environment
IS_TESTING = (
    'pytest' in sys.modules
    or any('pytest' in arg for arg in sys.argv)
    or os.environ.get('TESTING', 'False').lower() in ('true', '1')
)

ALLOWED_HOSTS = [host.strip() for host in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1' if not DEBUG else '*').split(',') if host.strip()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party packages
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'drf_spectacular_sidecar',  # serves Swagger/ReDoc assets locally (no CDN needed)
    'django_prometheus',

    # Local Domain Apps
    'apps.common',
    'apps.users',
    'apps.doctors',
    'apps.consultations',
    'apps.prescriptions',
    'apps.payments',
    'apps.audit',
    'apps.analytics',
    'apps.notifications',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'apps.common.middleware.RequestCorrelationIdMiddleware',
    'apps.common.middleware.MetricsCollectionMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.common.middleware.IdempotencyMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.audit.middleware.AuditLoggingMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'amrutam_core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'amrutam_core.wsgi.application'
ASGI_APPLICATION = 'amrutam_core.asgi.application'

# Database Configuration with Read-Replica Support
DB_ENGINE = os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3')
if DB_ENGINE == 'django.db.backends.postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'amrutam_db'),
            'USER': os.environ.get('DB_USER', 'amrutam_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '600')),
            'OPTIONS': {
                'connect_timeout': 5,
            },
        }
    }
    # Read-replica for offloading analytics, doctor search, and list queries
    _replica_host = os.environ.get('DB_REPLICA_HOST')
    if _replica_host:
        DATABASES['replica'] = {
            **DATABASES['default'],
            'HOST': _replica_host,
            'PORT': os.environ.get('DB_REPLICA_PORT', '5432'),
        }
        DATABASE_ROUTERS = ['apps.common.db_router.ReadReplicaRouter']
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 10},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static & Media Files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'apps.common.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/minute',
        'user': '1000/minute',
        'auth': '10/minute',
        'booking': '30/minute',
    },
    'EXCEPTION_HANDLER': 'apps.common.utils.custom_exception_handler',
}

# OpenAPI / drf-spectacular Settings (single authoritative block)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Amrutam Telemedicine API',
    'DESCRIPTION': (
        'Production-grade RESTful API for Amrutam Telemedicine & Ayurvedic Healthcare System. '
        'Supports end-to-end user lifecycle, high-concurrency doctor scheduling, race-condition protected bookings, '
        'tamper-evident audit trails, digital prescriptions, and admin analytics.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/v1/',
    # Self-host Swagger/ReDoc assets via sidecar — no CDN dependency
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',
}

# SimpleJWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.environ.get('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', '60'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.environ.get('JWT_REFRESH_TOKEN_LIFETIME_DAYS', '7'))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# (SPECTACULAR_SETTINGS defined above — duplicate block removed)

# Cache & Redis Configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'TIMEOUT': int(os.environ.get('CACHE_TTL', '300')),
    }
}

# Fallback to local memory cache if Redis is unavailable during local dev/tests
if DEBUG and not os.environ.get('FORCE_REDIS'):
    CACHES['default'] = {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'amrutam-local-mem-cache',
    }

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BEAT_SCHEDULE = {
    'release-expired-slots-every-minute': {
        'task': 'apps.consultations.tasks.release_expired_slots_task',
        'schedule': 60.0,
    },
    'aggregate-daily-analytics-midnight': {
        'task': 'apps.consultations.tasks.daily_analytics_rollup_task',
        'schedule': 86400.0,
    },
}
CELERY_TASK_ALWAYS_EAGER = IS_TESTING
CELERY_TASK_STORE_EAGER_RESULT = IS_TESTING

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',') if origin.strip()]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'idempotency-key',
    'x-correlation-id',
]

# Security Settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'



# HSTS (HTTP Strict Transport Security) — production only (not during testing or debug)
if not DEBUG and not IS_TESTING:
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    SECURE_SSL_REDIRECT = False

# PHI Encryption Key — must be set via environment in production
_encryption_key = os.environ.get('DATA_ENCRYPTION_KEY')
if not _encryption_key and not DEBUG:
    raise Exception(
        'SECURITY ERROR: DATA_ENCRYPTION_KEY is required in production. '
        'Generate with: python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"'
    )
DATA_ENCRYPTION_KEY = _encryption_key or 'dev-only-insecure-key-not-for-production'

# Razorpay Payment Gateway
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_amrutam2026')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')

# Notification Provider: 'log' (default), 'ses', or 'sendgrid'
NOTIFICATION_PROVIDER = os.environ.get('NOTIFICATION_PROVIDER', 'log')
NOTIFICATION_FROM_EMAIL = os.environ.get('NOTIFICATION_FROM_EMAIL', 'noreply@amrutam.com')

MFA_ISSUER = os.environ.get('MFA_ISSUER', 'AmrutamAyurveda')

# Structured JSON Logging Configuration
class JsonFormatter(logging.Formatter):
    """Production-grade JSON log formatter for ELK / CloudWatch ingestion."""
    def format(self, record):
        log_entry = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', 'no-trace'),
            'module': record.module,
            'funcName': record.funcName,
            'lineno': record.lineno,
        }
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': lambda: JsonFormatter(),
        },
        'verbose': {
            'format': '[{asctime}] [{levelname}] [req:{correlation_id}] {name}: {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'filters': {
        'correlation': {
            '()': 'apps.common.logging.CorrelationIdFilter',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'json' if not DEBUG else 'verbose',
            'filters': ['correlation'],
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('LOG_LEVEL', 'INFO'),
    },
}
