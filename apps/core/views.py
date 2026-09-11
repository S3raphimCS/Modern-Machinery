"""Служебные представления: проверка живости сервиса."""

from django.db import connection
from django.http import JsonResponse


def healthcheck(request):
    """Проверяет, что приложение поднялось и база отвечает.

    Используется healthcheck'ом Docker и внешним мониторингом.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # pragma: no cover
        return JsonResponse({"status": "error", "database": "down"}, status=503)
    return JsonResponse({"status": "ok", "database": "up"})
