"""Каталог техники: бренды, категории, типы и модели машин."""

import io
import logging
from pathlib import Path

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.urls import reverse
from treebeard.mp_tree import MP_Node

from apps.core.fields import URLField
from apps.core.models import (
    PublishableMixin,
    SeoMixin,
    SortableMixin,
    TimeStampedModel,
)

from .querysets import MachineQuerySet, VisibleQuerySet

logger = logging.getLogger(__name__)


class Brand(TimeStampedModel, SeoMixin, SortableMixin):
    """Komatsu, BOMAG, Manitou, Terex, Denyo, Generac, TECHKING."""

    slug = models.SlugField("Slug", max_length=120, unique=True)
    name = models.CharField("Название", max_length=120)
    logo = models.ImageField("Логотип", upload_to="brands/", blank=True, null=True)
    logo_hover = models.ImageField(
        "Логотип при наведении", upload_to="brands/", blank=True, null=True
    )
    description = models.TextField("Описание", blank=True)
    is_active = models.BooleanField("Активен", default=True, db_index=True)

    objects = VisibleQuerySet.as_manager()

    class Meta:
        verbose_name = "Бренд"
        verbose_name_plural = "Бренды"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Category(MP_Node, SeoMixin):
    """Дерево разделов каталога.

    Materialized Path вместо MPTT: категории читаются на каждой странице и
    меняются раз в месяц, а поддерево здесь достаётся одним запросом.
    """

    slug = models.SlugField("Slug", max_length=140, unique=True)
    name = models.CharField("Название", max_length=160)
    description = models.TextField("Описание", blank=True)
    image = models.ImageField("Картинка", upload_to="categories/", blank=True, null=True)
    is_active = models.BooleanField("Активна", default=True, db_index=True)

    node_order_by = ["name"]

    class Meta:
        verbose_name = "Категория техники"
        verbose_name_plural = "Категории техники"

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("catalog:machine-list") + f"?category={self.slug}"


class MachineType(TimeStampedModel, SortableMixin):
    """Экскаватор, бульдозер, погрузчик, каток, кран, генератор."""

    slug = models.SlugField("Slug", max_length=120, unique=True)
    name = models.CharField("Название", max_length=120)
    name_plural = models.CharField("Название во множественном числе", max_length=120)
    icon = models.FileField("Иконка", upload_to="types/", blank=True, null=True)

    class Meta:
        verbose_name = "Тип техники"
        verbose_name_plural = "Типы техники"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Machine(TimeStampedModel, SeoMixin, PublishableMixin, SortableMixin):
    """Модель техники в каталоге, например Komatsu PC400-8.

    Это именно модель, а не физическая единица. Парк клиента (`MachineUnit` с
    серийным номером) появится на этапе 2 и будет ссылаться сюда — поэтому
    каталог сразу проектируется как справочник моделей.
    """

    slug = models.SlugField("Slug", max_length=180, unique=True)
    name = models.CharField("Название", max_length=180)
    full_name = models.CharField("Полное название", max_length=255, blank=True)
    series = models.CharField("Серия", max_length=80, blank=True)

    brand = models.ForeignKey(
        Brand, verbose_name="Бренд", on_delete=models.PROTECT, related_name="machines"
    )
    machine_type = models.ForeignKey(
        MachineType, verbose_name="Тип", on_delete=models.PROTECT, related_name="machines"
    )
    categories = models.ManyToManyField(
        Category, verbose_name="Категории", related_name="machines", blank=True
    )

    short_description = models.TextField("Краткое описание", blank=True)
    description = models.TextField("Описание", blank=True)
    equipment = models.TextField("Комплектация", blank=True)
    warranty_note = models.CharField("Гарантия", max_length=160, blank=True)

    # Цена в B2B договорная, поэтому по умолчанию скрыта. Поля заведены потому,
    # что карточка в макете показывает цену, а филиал ведёт часть позиций с ней.
    price = models.DecimalField("Цена", max_digits=14, decimal_places=2, null=True, blank=True)
    price_note = models.CharField("Примечание к цене", max_length=160, blank=True)
    is_price_on_request = models.BooleanField("Цена по запросу", default=True)

    is_active = models.BooleanField("Активна", default=True, db_index=True)
    is_featured = models.BooleanField("Рекомендуемая", default=False)

    # Снимок характеристик для плитки каталога: пересчитывается сигналом.
    specs_cache = models.JSONField("Снимок характеристик", default=dict, blank=True)
    # Сырые данные импорта до нормализации: чтобы ничего не потерять.
    raw_specs = models.JSONField("Сырые характеристики", default=dict, blank=True)

    source_url = URLField("Источник", blank=True)
    source_hash = models.CharField("Хеш источника", max_length=64, blank=True)

    search_vector = SearchVectorField(null=True, editable=False)

    objects = MachineQuerySet.as_manager()

    class Meta:
        verbose_name = "Техника"
        verbose_name_plural = "Каталог техники"
        ordering = ["sort_order", "name"]
        indexes = [
            GinIndex(fields=["search_vector"], name="machine_search_gin"),
            # Индексы под поиск по опечаткам: без них похожесть считается
            # перебором всей таблицы.
            GinIndex(fields=["name"], name="machine_name_trgm", opclasses=["gin_trgm_ops"]),
            GinIndex(
                fields=["full_name"], name="machine_fullname_trgm", opclasses=["gin_trgm_ops"]
            ),
            GinIndex(
                fields=["specs_cache"], name="machine_specs_gin", opclasses=["jsonb_path_ops"]
            ),
            models.Index(fields=["brand", "machine_type"], name="machine_brand_type_idx"),
            models.Index(
                fields=["is_active", "is_published"],
                name="machine_visible_idx",
                condition=models.Q(is_active=True, is_published=True),
            ),
        ]

    def __str__(self) -> str:
        return self.full_name or f"{self.brand.name} {self.name}"

    def get_absolute_url(self) -> str:
        return reverse("catalog:machine-detail", kwargs={"slug": self.slug})

    @property
    def main_image(self):
        """Главное изображение или первое по порядку.

        Работает по уже загруженному `images`, чтобы не делать лишний запрос
        на каждую карточку в листинге.
        """
        images = list(self.images.all())
        for image in images:
            if image.is_main:
                return image
        return images[0] if images else None

    @property
    def display_price(self) -> str:
        if self.is_price_on_request or self.price is None:
            return "Цена по запросу"
        return f"{self.price:,.0f} ₽".replace(",", " ")

    @property
    def stock_status(self) -> str:
        """Сводный статус наличия по всем складам."""
        statuses = {stock.status for stock in self.stocks.all()}
        for status in (
            MachineStock.Status.IN_STOCK,
            MachineStock.Status.LOW,
            MachineStock.Status.ON_ORDER,
        ):
            if status in statuses:
                return status
        return MachineStock.Status.NONE


class CatalogLanding(TimeStampedModel, SeoMixin, PublishableMixin, SortableMixin):
    """Посадочная страница каталога под конкретный запрос.

    Подборка вида `/?brand=komatsu&type=ekskavator` поисковиком почти не
    ранжируется: у неё нет собственного адреса, заголовка и текста. Та же
    выдача по адресу `/katalog/ekskavatory-komatsu/` с заголовком
    «Экскаваторы Komatsu в Хабаровске» — полноценная страница под геозапрос,
    а региональные запросы и есть основной источник трафика для филиала
    (раздел 7.3 плана).

    Условия отбора хранятся полями, а не строкой параметров: так подборку
    видно в админке и её нельзя случайно сломать опечаткой в query-строке.
    """

    slug = models.SlugField("Slug", max_length=160, unique=True)
    title = models.CharField("Заголовок", max_length=200)
    intro = models.TextField(
        "Вступительный текст",
        blank=True,
        help_text="Уникальный текст под запрос. Копировать описания с корпоративного "
        "сайта нельзя — это прямые дубли на одном домене.",
    )

    brand = models.ForeignKey(
        Brand,
        verbose_name="Бренд",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="landings",
    )
    machine_type = models.ForeignKey(
        MachineType,
        verbose_name="Тип техники",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="landings",
    )
    category = models.ForeignKey(
        Category,
        verbose_name="Категория",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="landings",
    )
    is_featured = models.BooleanField(
        "Показывать в каталоге",
        default=True,
        help_text="Ссылка на подборку выводится под списком техники: внутренняя "
        "перелинковка помогает индексации.",
    )

    class Meta:
        verbose_name = "Подборка каталога"
        verbose_name_plural = "Подборки каталога"
        ordering = ["sort_order", "title"]
        constraints = [
            # Подборка без единого условия дублировала бы каталог целиком.
            models.CheckConstraint(
                name="cataloglanding_has_condition",
                condition=(
                    models.Q(brand__isnull=False)
                    | models.Q(machine_type__isnull=False)
                    | models.Q(category__isnull=False)
                ),
            )
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("catalog:landing", kwargs={"slug": self.slug})


class CatalogLandingSpec(models.Model):
    """Условие подборки по числовой характеристике.

    Даёт посадочные страницы под запросы вида «экскаватор 20 тонн»: у
    конкурента такие разделы есть, а это ровно та региональная низкочастотка,
    ради которой затевался проект.

    Условий на подборку может быть несколько — например, тип «Экскаватор»
    плюс масса от 20 до 25 тонн.
    """

    landing = models.ForeignKey(
        CatalogLanding,
        verbose_name="Подборка",
        on_delete=models.CASCADE,
        related_name="spec_conditions",
    )
    spec_key = models.ForeignKey(
        "specs.SpecKey",
        verbose_name="Параметр",
        on_delete=models.CASCADE,
        related_name="landing_conditions",
    )
    value_min = models.DecimalField("От", max_digits=14, decimal_places=4, null=True, blank=True)
    value_max = models.DecimalField("До", max_digits=14, decimal_places=4, null=True, blank=True)

    class Meta:
        verbose_name = "Условие по характеристике"
        verbose_name_plural = "Условия по характеристикам"
        ordering = ["spec_key__sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["landing", "spec_key"], name="cataloglandingspec_unique_key"
            ),
            # Условие без границ не фильтрует ничего и только сбивает подсчёт
            # для правила индексации.
            models.CheckConstraint(
                name="cataloglandingspec_has_bound",
                condition=models.Q(value_min__isnull=False) | models.Q(value_max__isnull=False),
            ),
            models.CheckConstraint(
                name="cataloglandingspec_range_ordered",
                condition=models.Q(value_min__isnull=True)
                | models.Q(value_max__isnull=True)
                | models.Q(value_max__gte=models.F("value_min")),
            ),
        ]

    def __str__(self) -> str:
        if self.value_min is not None and self.value_max is not None:
            return f"{self.spec_key.name}: {self.value_min}–{self.value_max}"
        if self.value_min is not None:
            return f"{self.spec_key.name}: от {self.value_min}"
        return f"{self.spec_key.name}: до {self.value_max}"


class MachineImage(SortableMixin):
    """Изображение из галереи модели.

    Рядом с исходником хранятся две производные: копия в WebP и превью для
    плитки каталога. Исходник остаётся нетронутым — контент-менеджер загружает
    файл как есть, а сайт отдаёт лёгкие версии.
    """

    machine = models.ForeignKey(
        Machine, verbose_name="Техника", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField("Изображение", upload_to="machines/%Y/%m/")
    # Производные пересчитываются автоматически, руками их менять не нужно.
    image_webp = models.ImageField(
        "Копия в WebP", upload_to="machines/%Y/%m/webp/", blank=True, editable=False
    )
    thumbnail = models.ImageField(
        "Превью", upload_to="machines/%Y/%m/thumb/", blank=True, editable=False
    )
    alt = models.CharField("Альтернативный текст", max_length=255, blank=True)
    is_main = models.BooleanField("Главное", default=False)

    class Meta:
        verbose_name = "Изображение техники"
        verbose_name_plural = "Изображения техники"
        ordering = ["sort_order", "id"]
        constraints = [
            # Частичный уникальный индекс: без него у карточки рано или поздно
            # окажется две «главных» картинки и вёрстка поедет.
            models.UniqueConstraint(
                fields=["machine"],
                condition=models.Q(is_main=True),
                name="one_main_image_per_machine",
            )
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Запоминаем исходный файл, чтобы пересобирать производные только при
        # его замене, а не на каждом сохранении порядка сортировки.
        self._initial_image = self.image.name if self.image else ""

    def __str__(self) -> str:
        return self.alt or f"Изображение {self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        image_changed = (self.image.name if self.image else "") != self._initial_image
        needs_build = bool(self.image) and (image_changed or not self.thumbnail)
        if needs_build:
            self.build_derivatives()

    def build_derivatives(self) -> None:
        """Пересобирает копию в WebP и превью.

        Ошибка обработки не должна ронять сохранение карточки: без превью сайт
        покажет исходник, а вот потерянная при загрузке карточка — это работа
        контент-менеджера заново.
        """
        from django.core.files.base import ContentFile

        from .services.images import make_thumbnail, make_webp

        try:
            with self.image.open("rb") as source:
                payload = source.read()
            webp = make_webp(io.BytesIO(payload))
            thumb = make_thumbnail(io.BytesIO(payload))
        except (OSError, ValueError) as exc:
            logger.warning("Не удалось обработать изображение %s: %s", self.pk, exc)
            return

        stem = Path(self.image.name).stem
        self.image_webp.save(f"{stem}.webp", ContentFile(webp), save=False)
        self.thumbnail.save(f"{stem}-thumb.webp", ContentFile(thumb), save=False)
        self._initial_image = self.image.name
        super().save(update_fields=["image_webp", "thumbnail"])

    @property
    def display_url(self) -> str:
        """Адрес для показа: WebP, если он собран, иначе исходник."""
        return self.image_webp.url if self.image_webp else self.image.url

    @property
    def thumbnail_url(self) -> str:
        """Адрес превью для плитки каталога."""
        return self.thumbnail.url if self.thumbnail else self.display_url


class MachineDocument(SortableMixin):
    """PDF-документ: брошюра, спецификация, сертификат, руководство."""

    class Kind(models.TextChoices):
        BROCHURE = "brochure", "Брошюра"
        SPEC = "spec", "Техническая спецификация"
        CERTIFICATE = "certificate", "Сертификат"
        MANUAL = "manual", "Руководство"

    machine = models.ForeignKey(
        Machine, verbose_name="Техника", on_delete=models.CASCADE, related_name="documents"
    )
    kind = models.CharField("Тип", max_length=20, choices=Kind.choices, default=Kind.BROCHURE)
    title = models.CharField("Название", max_length=255)
    file = models.FileField("Файл", upload_to="docs/%Y/")
    file_size = models.PositiveIntegerField("Размер, байт", default=0)

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.title


class MachineStock(models.Model):
    """Наличие модели на складе филиала.

    Макет показывает «В наличии · 2 ед.» и срок готовности к выдаче, поэтому
    склад заведён и для техники, а не только для запчастей. Публично отдаётся
    статус, точное количество остаётся внутренним полем.
    """

    class Status(models.TextChoices):
        IN_STOCK = "in_stock", "В наличии"
        LOW = "low", "Мало"
        ON_ORDER = "on_order", "Под заказ"
        NONE = "none", "Нет"

    machine = models.ForeignKey(
        Machine, verbose_name="Техника", on_delete=models.CASCADE, related_name="stocks"
    )
    branch = models.ForeignKey(
        "company.Branch",
        verbose_name="Филиал",
        on_delete=models.CASCADE,
        related_name="machine_stocks",
    )
    status = models.CharField("Статус", max_length=16, choices=Status.choices, default=Status.NONE)
    quantity = models.PositiveIntegerField("Количество", null=True, blank=True)
    lead_time = models.CharField("Срок готовности", max_length=120, blank=True)
    synced_at = models.DateTimeField("Синхронизировано", null=True, blank=True)

    class Meta:
        verbose_name = "Наличие техники"
        verbose_name_plural = "Наличие техники"
        constraints = [
            models.UniqueConstraint(fields=["machine", "branch"], name="machinestock_unique_branch")
        ]

    def __str__(self) -> str:
        return f"{self.machine}: {self.get_status_display()}"
