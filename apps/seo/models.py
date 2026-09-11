"""Карта редиректов и мониторинг 404.

Рабочий цикл после запуска: смотрим `NotFoundLog` по убыванию попаданий,
добавляем правило в `RedirectRule`, помечаем запись решённой. За две недели
так закрывается почти весь хвост старых ссылок.
"""

from django.db import models


class RedirectRule(models.Model):
    """Правило переадресации со старого адреса на новый."""

    old_path = models.CharField("Старый путь", max_length=500, unique=True, db_index=True)
    new_path = models.CharField("Новый путь", max_length=500)
    status_code = models.PositiveSmallIntegerField(
        "Код ответа",
        default=301,
        choices=[(301, "301 — постоянный"), (302, "302 — временный")],
    )
    is_active = models.BooleanField("Активно", default=True, db_index=True)
    is_auto = models.BooleanField("Создано автоматически", default=False)
    hits = models.PositiveIntegerField("Срабатываний", default=0)
    last_hit_at = models.DateTimeField("Последнее срабатывание", null=True, blank=True)
    note = models.CharField("Примечание", max_length=255, blank=True)

    class Meta:
        verbose_name = "Редирект"
        verbose_name_plural = "Редиректы"
        ordering = ["-hits", "old_path"]

    def __str__(self) -> str:
        return f"{self.old_path} → {self.new_path}"


class NotFoundLog(models.Model):
    """Агрегированный лог несуществующих адресов."""

    path = models.CharField("Путь", max_length=500, unique=True, db_index=True)
    referrer = models.CharField("Источник перехода", max_length=500, blank=True)
    hits = models.PositiveIntegerField("Обращений", default=1)
    first_seen = models.DateTimeField("Впервые", auto_now_add=True)
    last_seen = models.DateTimeField("Последний раз", auto_now=True)
    is_resolved = models.BooleanField("Обработано", default=False, db_index=True)

    class Meta:
        verbose_name = "Ненайденный адрес"
        verbose_name_plural = "Ненайденные адреса (404)"
        ordering = ["-hits", "-last_seen"]

    def __str__(self) -> str:
        return f"{self.path} ({self.hits})"
