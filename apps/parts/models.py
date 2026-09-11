"""Каталог запасных частей.

Главное отличие от техники — объём. Моделей техники сотни, артикулов при полной
выгрузке из 1С — десятки тысяч. Поэтому здесь нет EAV: плоская таблица с
правильными индексами и поиском по нормализованному артикулу.
"""

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.urls import reverse
from treebeard.mp_tree import MP_Node

from apps.core.models import PublishableMixin, SeoMixin, TimeStampedModel
from apps.core.utils import normalize_article


class PartCategory(MP_Node, SeoMixin):
    """Оригинальные, ходовая часть, фильтры, ковши, гидромолоты, РВД, шины."""

    slug = models.SlugField("Slug", max_length=140, unique=True)
    name = models.CharField("Название", max_length=160)
    description = models.TextField("Описание", blank=True)
    is_active = models.BooleanField("Активна", default=True, db_index=True)

    node_order_by = ["name"]

    class Meta:
        verbose_name = "Категория запчастей"
        verbose_name_plural = "Категории запчастей"

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("parts:part-list") + f"?category={self.slug}"


class PartQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(is_active=True, is_published=True)

    def search(self, query: str):
        """Ищет по названию и по артикулу в любом написании."""
        query = (query or "").strip()
        if not query:
            return self
        return self.filter(
            models.Q(name__icontains=query)
            | models.Q(article__icontains=query)
            | models.Q(article_norm__contains=normalize_article(query))
        )


class Part(TimeStampedModel, PublishableMixin):
    """Позиция каталога запчастей."""

    article = models.CharField("Артикул", max_length=64)
    # Артикул без разделителей и регистра. Снабженец вводит «600 311 3750»,
    # «600-311-3750» или «6003113750» — находиться должно во всех трёх случаях.
    article_norm = models.CharField("Артикул (нормализованный)", max_length=64, db_index=True)
    brand = models.ForeignKey(
        "catalog.Brand", verbose_name="Бренд", on_delete=models.PROTECT, related_name="parts"
    )
    category = models.ForeignKey(
        PartCategory, verbose_name="Категория", on_delete=models.PROTECT, related_name="parts"
    )

    name = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    is_original = models.BooleanField("Оригинальная", default=True)
    unit = models.CharField("Единица", max_length=16, default="шт")
    weight_kg = models.DecimalField(
        "Вес, кг", max_digits=10, decimal_places=3, null=True, blank=True
    )
    image = models.ImageField("Изображение", upload_to="parts/", blank=True, null=True)

    is_active = models.BooleanField("Активна", default=True, db_index=True)
    external_id = models.CharField("Ключ 1С", max_length=64, blank=True, db_index=True)

    objects = PartQuerySet.as_manager()

    class Meta:
        verbose_name = "Запчасть"
        verbose_name_plural = "Запчасти"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["brand", "article"], name="part_unique_article")
        ]
        indexes = [
            GinIndex(fields=["name"], name="part_name_trgm", opclasses=["gin_trgm_ops"]),
            GinIndex(fields=["article_norm"], name="part_article_trgm", opclasses=["gin_trgm_ops"]),
        ]

    def __str__(self) -> str:
        return f"{self.article} — {self.name}"

    def save(self, *args, **kwargs):
        # Нормализованный артикул считается всегда, а не только при импорте:
        # иначе позиция, заведённая руками в админке, не найдётся поиском.
        self.article_norm = normalize_article(self.article)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("parts:part-detail", kwargs={"pk": self.pk})

    @property
    def stock_status(self) -> str:
        statuses = {stock.status for stock in self.stocks.all()}
        for status in (PartStock.Status.IN_STOCK, PartStock.Status.LOW, PartStock.Status.ON_ORDER):
            if status in statuses:
                return status
        return PartStock.Status.NONE


class PartApplicability(models.Model):
    """Какая запчасть к какой модели техники подходит."""

    part = models.ForeignKey(
        Part, verbose_name="Запчасть", on_delete=models.CASCADE, related_name="applicability"
    )
    machine = models.ForeignKey(
        "catalog.Machine", verbose_name="Техника", on_delete=models.CASCADE, related_name="parts"
    )
    note = models.CharField("Примечание", max_length=255, blank=True)

    class Meta:
        verbose_name = "Применимость"
        verbose_name_plural = "Применимость"
        constraints = [
            models.UniqueConstraint(fields=["part", "machine"], name="partapplicability_unique")
        ]

    def __str__(self) -> str:
        return f"{self.part.article} → {self.machine}"


class PartAnalog(models.Model):
    """Аналог или замена артикула."""

    class Kind(models.TextChoices):
        ANALOG = "analog", "Аналог"
        REPLACEMENT = "replacement", "Заменён на"

    part = models.ForeignKey(
        Part, verbose_name="Запчасть", on_delete=models.CASCADE, related_name="analogs"
    )
    analog = models.ForeignKey(
        Part, verbose_name="Аналог", on_delete=models.CASCADE, related_name="analog_for"
    )
    kind = models.CharField("Тип", max_length=16, choices=Kind.choices, default=Kind.ANALOG)

    class Meta:
        verbose_name = "Аналог"
        verbose_name_plural = "Аналоги"
        constraints = [
            models.UniqueConstraint(fields=["part", "analog"], name="partanalog_unique"),
            # Запчасть не может быть аналогом самой себе.
            models.CheckConstraint(
                name="partanalog_not_self",
                condition=~models.Q(part=models.F("analog")),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.part.article} ≈ {self.analog.article}"


class PartStock(models.Model):
    """Наличие запчасти на складе филиала.

    Точное количество намеренно не публичное: показывать конкурентам остатки
    склада заказчик не захочет. Наружу отдаётся статус.
    """

    class Status(models.TextChoices):
        IN_STOCK = "in_stock", "В наличии"
        LOW = "low", "Мало"
        ON_ORDER = "on_order", "Под заказ"
        NONE = "none", "Нет"

    part = models.ForeignKey(
        Part, verbose_name="Запчасть", on_delete=models.CASCADE, related_name="stocks"
    )
    branch = models.ForeignKey(
        "company.Branch", verbose_name="Филиал", on_delete=models.CASCADE, related_name="stocks"
    )
    status = models.CharField("Статус", max_length=16, choices=Status.choices, default=Status.NONE)
    quantity = models.PositiveIntegerField("Количество", null=True, blank=True)
    lead_time = models.CharField("Срок поставки", max_length=120, blank=True)
    synced_at = models.DateTimeField("Синхронизировано", null=True, blank=True)

    class Meta:
        verbose_name = "Наличие запчасти"
        verbose_name_plural = "Наличие запчастей"
        constraints = [
            models.UniqueConstraint(fields=["part", "branch"], name="partstock_unique_branch")
        ]

    def __str__(self) -> str:
        return f"{self.part.article}: {self.get_status_display()}"


# Наборы статусов склада у техники и запчастей совпадают, поэтому в схеме API
# это один enum. Константа объявлена на уровне модуля ради drf-spectacular.
STOCK_STATUS_CHOICES = PartStock.Status.choices
