# syntax=docker/dockerfile:1

# ---------- Стадия сборки ----------
# Зависимости ставятся отдельным слоем: рантайм не должен тащить компиляторы
# и кэш сборки. Образ получается заметно меньше и с меньшей поверхностью атаки.
FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Сначала только манифесты: слой с зависимостями переиспользуется, пока
# pyproject.toml и uv.lock не изменились.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------- Рантайм ----------
FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.production

# libpq нужен psycopg, curl — healthcheck'у контейнера.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Приложение работает от непривилегированного пользователя: процесс в
# контейнере не должен иметь права root ни при каких обстоятельствах.
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --create-home app

WORKDIR /app

COPY --from=builder --chown=app:app /app /app

# Каталог /app остаётся недоступным приложению на запись — это нарочно.
# Всё, что пишется в рантайме, живёт в отдельных каталогах.
RUN mkdir -p /app/media /app/staticfiles /var/lib/celery \
    && chown -R app:app /app/media /app/staticfiles /var/lib/celery

COPY --chown=app:app compose/production/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER app

EXPOSE 8000

# Проверка живости обращается к приложению изнутри контейнера, но обязана
# представиться настоящим доменом. Django сверяет заголовок Host со списком
# ALLOWED_HOSTS и отвечает 400 на «127.0.0.1:8000» — проверка падала бы на
# любом сервере, где в списке указан рабочий домен, а не localhost.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent --header "Host: ${DOMAIN:-localhost}" \
        http://127.0.0.1:8000/healthz/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--threads", "2", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
