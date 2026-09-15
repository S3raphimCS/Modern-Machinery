"""Базовые настройки, общие для всех окружений."""

from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    env.read_env(str(env_file))

# --- Основное -------------------------------------------------------------

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
SITE_URL = env("SITE_URL", default="http://localhost:8000")

# --- Приложения -----------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "treebeard",
    "corsheaders",
]

LOCAL_APPS = [
    "apps.core",
    "apps.users",
    "apps.company",
    "apps.specs",
    "apps.catalog",
    "apps.parts",
    "apps.services",
    "apps.content",
    "apps.leads",
    "apps.seo",
    "apps.imports",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# --- Middleware -----------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.ContentSecurityPolicyMiddleware",
    # Оба SEO-middleware работают только на ответах 404, поэтому стоят последними.
    #
    # Порядок важен: ответы проходят middleware в обратном порядке, поэтому
    # логирование объявлено раньше и получает ответ уже после того, как
    # редиректы отработали. Иначе в журнал 404 попадали бы адреса, которые
    # на самом деле успешно переадресуются.
    "apps.seo.middleware.NotFoundLoggingMiddleware",
    "apps.seo.middleware.RedirectFallbackMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.content.context_processors.site_context",
            ],
        },
    },
]

# --- База данных ----------------------------------------------------------

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

# --- Кэш ------------------------------------------------------------------

# Бэкенд кэша задаётся переменной окружения: в production это Redis, а для
# машины без него (локальная разработка, прогон тестов в CI) достаточно
# указать `locmem://`. Приложение при этом не меняется — фасеты каталога,
# меню и настройки сайта одинаково кэшируются в обоих режимах.
CACHE_URL = env("CACHE_URL", default=env("REDIS_URL", default="redis://127.0.0.1:6379/0"))

if CACHE_URL.startswith("locmem"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "mm",
        }
    }
elif CACHE_URL.startswith("dummy"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": CACHE_URL,
            "KEY_PREFIX": "mm",
        }
    }

# --- Celery ---------------------------------------------------------------

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = "Asia/Vladivostok"
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "purge-expired-leads": {
        "task": "apps.leads.tasks.purge_expired_leads",
        # Каждый день в 03:30 по времени филиала.
        "schedule": crontab(hour=3, minute=30),
    },
}

# --- Пароли и аутентификация ----------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "admin:login"

# --- Локализация ----------------------------------------------------------

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Asia/Vladivostok"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

# --- Статика и медиа ------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

USE_S3 = env.bool("USE_S3", default=False)

if USE_S3:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "access_key": env("AWS_ACCESS_KEY_ID"),
                "secret_key": env("AWS_SECRET_ACCESS_KEY"),
                "bucket_name": env("AWS_STORAGE_BUCKET_NAME"),
                "endpoint_url": env("AWS_S3_ENDPOINT_URL", default=None),
                "region_name": env("AWS_S3_REGION_NAME", default=""),
                "file_overwrite": False,
                "querystring_auth": False,
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

# --- Почта ----------------------------------------------------------------

vars().update(env.email_url("EMAIL_URL", default="consolemail://"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="site@modernmachinery.example")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
LEADS_FALLBACK_EMAIL = env("LEADS_FALLBACK_EMAIL", default=DEFAULT_FROM_EMAIL)

# Домены, на которые сайт отказывается отправлять письма о заявках.
#
# Предохранитель для демонстрационных площадок: не даёт заявке уйти на почту
# настоящей компании, если её адрес остался в правилах маршрутизации или его
# вписали в админке по невнимательности.
#
# На рабочем сайте компании список обязан быть пустым — иначе он заблокирует
# её собственную почту.
LEADS_BLOCKED_EMAIL_DOMAINS = [
    domain.strip().lower().lstrip("@")
    for domain in env.list("LEADS_BLOCKED_EMAIL_DOMAINS", default=[])
    if domain.strip()
]

# --- Защита форм заявок ---------------------------------------------------

LEAD_THROTTLE_RATE = env("LEAD_THROTTLE_RATE", default="20/hour")
LEAD_THROTTLE_BURST_RATE = env("LEAD_THROTTLE_BURST_RATE", default="3/min")
LEAD_MIN_FORM_SECONDS = env.int("LEAD_MIN_FORM_SECONDS", default=3)
LEAD_DEDUPE_WINDOW_SECONDS = env.int("LEAD_DEDUPE_WINDOW_SECONDS", default=300)
LEAD_RETENTION_DAYS = env.int("LEAD_RETENTION_DAYS", default=365)

# --- Каталог --------------------------------------------------------------

CATALOG_PAGE_SIZE = env.int("CATALOG_PAGE_SIZE", default=12)
# Автодополнение поиска: за каждым нажатием клавиши стоит полнотекстовый
# запрос, поэтому частота ограничена так же, как у формы заявок.
SEARCH_THROTTLE_RATE = env("SEARCH_THROTTLE_RATE", default="120/min")
CATALOG_FACETS_CACHE_SECONDS = env.int("CATALOG_FACETS_CACHE_SECONDS", default=900)

# --- DRF ------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.api.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("ANON_THROTTLE_RATE", default="240/min"),
        "user": env("USER_THROTTLE_RATE", default="1000/min"),
        # Две независимые корзины на создание заявки: длинное окно от массового
        # налива в базу и короткое от всплеска в несколько секунд.
        "leads": LEAD_THROTTLE_RATE,
        "leads-burst": LEAD_THROTTLE_BURST_RATE,
        "search": SEARCH_THROTTLE_RATE,
    },
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Модерн Машинери Фар Ист — API филиала в Хабаровске",
    "DESCRIPTION": (
        "Публичный API каталога техники, запчастей и услуг. "
        "Чтение доступно анонимно, создание заявок ограничено дросселированием."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "SORT_OPERATIONS": False,
    # У заявки, склада техники и склада запчастей поля называются одинаково
    # ("status"), но наборы значений разные. Без явных имён схема получает
    # автосгенерированные вроде "Status1ccEnum", нечитаемые для потребителя API.
    "ENUM_NAME_OVERRIDES": {
        "LeadStatusEnum": "apps.leads.models.LEAD_STATUS_CHOICES",
        "StockStatusEnum": "apps.parts.models.STOCK_STATUS_CHOICES",
    },
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_URLS_REGEX = r"^/api/.*$"

# --- Безопасность ---------------------------------------------------------

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # HTMX читает токен из cookie
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# --- Логирование ----------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "apps": {
            "level": env("LOG_LEVEL", default="INFO"),
            "handlers": ["console"],
            "propagate": False,
        },
    },
}
