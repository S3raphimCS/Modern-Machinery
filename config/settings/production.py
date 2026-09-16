"""Настройки для production."""

from .base import *
from .base import env

DEBUG = False

# Список хостов обязателен: с "*" в проде ловим Host header poisoning.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
# Проверка живости приходит по http с петлевого интерфейса — от healthcheck
# контейнера и от внешнего мониторинга. Отправлять её на https нельзя: пока
# сертификат ещё не выпущен, https не отвечает, и nginx на свежем сервере
# уходит в unhealthy, хотя работает и обслуживает проверку Let's Encrypt.
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Sentry подключается только если задан DSN: без него приложение работает как обычно.
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:  # pragma: no cover
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=env("SENTRY_ENVIRONMENT", default="production"),
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),
        send_default_pii=False,
    )

# На проде счётчик нужен всегда. Выключается явной переменной окружения —
# например на предпроде с копией боевой базы.
METRIKA_ENABLED = env.bool("METRIKA_ENABLED", default=True)
