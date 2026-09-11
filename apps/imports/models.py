"""Учёт импортов и инвентаризация источников."""

from django.db import models

from apps.core.fields import URLField


class SourcePage(models.Model):
    """Страница старого сайта.

    Инвентаризация нужна для двух вещей: оценить объём переноса и построить
    черновик карты редиректов. `content_hash` даёт идемпотентность — повторный
    прогон пропускает неизменившиеся страницы.
    """

    class PageType(models.TextChoices):
        MACHINE = "machine", "Карточка техники"
        CATALOG = "catalog", "Раздел каталога"
        PART = "part", "Запчасти"
        CONTENT = "content", "Текстовая страница"
        NEWS = "news", "Новость"
        CONTACTS = "contacts", "Контакты"
        JUNK = "junk", "Не переносим"

    url = URLField("Адрес", max_length=500, unique=True)
    path = models.CharField("Путь", max_length=500, db_index=True)
    http_status = models.PositiveSmallIntegerField("Код ответа", default=200)
    page_type = models.CharField(
        "Тип страницы", max_length=20, choices=PageType.choices, blank=True
    )
    title = models.CharField("Title", max_length=255, blank=True)
    meta_description = models.TextField("Meta description", blank=True)
    content_hash = models.CharField("Хеш содержимого", max_length=64, blank=True)
    fetched_at = models.DateTimeField("Загружено", null=True, blank=True)
    raw_path = models.CharField("Путь к кэшу HTML", max_length=500, blank=True)
    is_migrated = models.BooleanField("Перенесено", default=False, db_index=True)
    target_path = models.CharField("Новый путь", max_length=500, blank=True)

    class Meta:
        verbose_name = "Страница источника"
        verbose_name_plural = "Страницы источника"
        ordering = ["path"]

    def __str__(self) -> str:
        return self.path


class ImportRun(models.Model):
    """Прогон импорта.

    Нужен для отчётности: «перенесено 412 из 460 страниц, 48 помечены как не
    подлежащие переносу» — это то, что заказчик хочет видеть в конце этапа.
    """

    class Status(models.TextChoices):
        RUNNING = "running", "Выполняется"
        SUCCESS = "success", "Успешно"
        FAILED = "failed", "Ошибка"

    source = models.CharField("Источник", max_length=40)
    kind = models.CharField("Что импортировали", max_length=40)
    status = models.CharField(
        "Статус", max_length=16, choices=Status.choices, default=Status.RUNNING
    )
    started_at = models.DateTimeField("Начало", auto_now_add=True)
    finished_at = models.DateTimeField("Окончание", null=True, blank=True)
    stats = models.JSONField("Статистика", default=dict)
    log = models.TextField("Журнал", blank=True)

    class Meta:
        verbose_name = "Прогон импорта"
        verbose_name_plural = "Прогоны импорта"
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.kind} от {self.started_at:%d.%m.%Y %H:%M} — {self.get_status_display()}"

    def finish(self, *, status: str, stats: dict | None = None, log: str = "") -> None:
        """Закрывает прогон с итоговой статистикой."""
        from django.utils import timezone

        self.status = status
        self.finished_at = timezone.now()
        if stats is not None:
            self.stats = stats
        if log:
            self.log = log
        self.save(update_fields=["status", "finished_at", "stats", "log"])
