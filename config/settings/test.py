"""Настройки для прогона тестов."""

import tempfile
from pathlib import Path

from .base import *
from .base import DATABASES, REST_FRAMEWORK

DEBUG = False
ALLOWED_HOSTS = ["*", "testserver"]

# Быстрое хеширование: иначе создание пользователей в фикстурах доминирует по времени.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Кэш в памяти: тесты не должны зависеть от запущенного Redis.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "mm-tests",
    }
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Вложения к заявкам пишутся настоящим хранилищем: у поля задан свой
# storage, и подмена STORAGES на него не влияет. Каталог уводится во
# временный, иначе тесты копят файлы в репозитории.
PRIVATE_MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="mm-test-private-"))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Дросселирование выключено по умолчанию: тест, который его проверяет,
# включает нужную ставку через override_settings, а остальным тестам счётчик
# запросов только мешал бы.
LEAD_THROTTLE_RATE = None
LEAD_THROTTLE_BURST_RATE = None
SEARCH_THROTTLE_RATE = None

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        "anon": None,
        "user": None,
        "leads": None,
        "leads-burst": None,
        "search": None,
    },
}

DATABASES["default"]["ATOMIC_REQUESTS"] = True
