"""Middleware SEO-слоя.

Оба обработчика вмешиваются только в ответы 404, поэтому не добавляют работы
на нормальном пути запроса.
"""

import logging

from django.db.models import F
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.utils import timezone

from .models import NotFoundLog, RedirectRule

logger = logging.getLogger(__name__)

# Пути, по которым 404 — норма, а не потерянная ссылка.
IGNORED_PREFIXES = ("/static/", "/media/", "/favicon.ico", "/apple-touch-icon")


class RedirectFallbackMiddleware:
    """Переадресует старые адреса по таблице `RedirectRule`."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 404:
            return response

        path = request.path
        rule = RedirectRule.objects.filter(old_path=path, is_active=True).first()
        if rule is None and not path.endswith("/"):
            rule = RedirectRule.objects.filter(old_path=f"{path}/", is_active=True).first()
        if rule is None:
            return response

        # Счётчик обновляется через F(), чтобы параллельные запросы не затирали
        # результат друг друга.
        RedirectRule.objects.filter(pk=rule.pk).update(
            hits=F("hits") + 1, last_hit_at=timezone.now()
        )
        redirect_class = (
            HttpResponsePermanentRedirect if rule.status_code == 301 else HttpResponseRedirect
        )
        return redirect_class(rule.new_path)


class NotFoundLoggingMiddleware:
    """Копит статистику по несуществующим адресам."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 404:
            return response

        path = request.path[:500]
        if path.startswith(IGNORED_PREFIXES):
            return response

        referrer = request.META.get("HTTP_REFERER", "")[:500]
        try:
            updated = NotFoundLog.objects.filter(path=path).update(hits=F("hits") + 1)
            if not updated:
                NotFoundLog.objects.create(path=path, referrer=referrer)
        except Exception:  # pragma: no cover
            # Логирование 404 не должно ломать отдачу самой страницы 404.
            logger.exception("Не удалось записать 404 для %s", path)
        return response
