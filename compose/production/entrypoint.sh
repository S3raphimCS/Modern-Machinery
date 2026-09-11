#!/bin/sh
# Точка входа контейнера приложения.
#
# Миграции и сборка статики выполняются до старта веб-сервера: контейнер должен
# подниматься в рабочее состояние сам, без ручных шагов при деплое.
set -e

echo "Ожидание базы данных..."
python - <<'PY'
import os
import sys
import time

import psycopg

dsn = os.environ["DATABASE_URL"]
for attempt in range(60):
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            print("База данных доступна.")
            break
    except psycopg.OperationalError:
        time.sleep(1)
else:
    print("База данных не ответила за 60 секунд.", file=sys.stderr)
    raise SystemExit(1)
PY

echo "Применение миграций..."
python manage.py migrate --no-input

echo "Сборка статики..."
python manage.py collectstatic --no-input --clear

exec "$@"
