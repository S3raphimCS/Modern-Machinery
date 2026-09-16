"""Филиал, отделы, сотрудники и контакты.

Филиал в проекте один — хабаровский, — но модель `Branch` сохранена (раздел 7.4
плана): на ней висят сотрудники, контакты и складские остатки. Схлопнуть её в
настройки сайта — сэкономить день сейчас и переписывать три модуля при расширении
на Артём или Южно-Сахалинск.
"""

from django.db import models

from apps.core.models import PublishableMixin, SeoMixin, SortableMixin, TimeStampedModel


class Branch(TimeStampedModel, SeoMixin, PublishableMixin, SortableMixin):
    """Филиал компании."""

    slug = models.SlugField("Slug", max_length=120, unique=True)
    city = models.CharField("Город", max_length=120)
    is_head_office = models.BooleanField("Головной офис", default=False)

    address = models.CharField("Адрес", max_length=255)
    postcode = models.CharField("Индекс", max_length=10, blank=True)
    latitude = models.DecimalField("Широта", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(
        "Долгота", max_digits=9, decimal_places=6, null=True, blank=True
    )
    # Магадан, Хабаровск и Петропавловск живут в разных поясах: «работаем с 9:00»
    # без указания зоны вводит в заблуждение.
    timezone = models.CharField("Часовой пояс", max_length=40, default="Asia/Vladivostok")
    work_hours = models.CharField("График работы", max_length=255, blank=True)
    description = models.TextField("Описание", blank=True)

    class Meta:
        verbose_name = "Филиал"
        verbose_name_plural = "Филиалы"
        ordering = ["sort_order", "city"]

    def __str__(self) -> str:
        return self.city

    def get_absolute_url(self) -> str:
        return f"/o-kompanii/{self.slug}/"


class DeliveryOption(SortableMixin):
    """Способ доставки техники до объекта.

    Для Дальнего Востока это вопрос первого разговора: расстояния такие, что
    «как привезут» выясняют раньше, чем характеристики. Поэтому способы
    доставки показываются и отдельной страницей, и блоком прямо на карточке
    техники.
    """

    name = models.CharField("Название", max_length=160)
    description = models.TextField("Описание", blank=True)
    lead_time = models.CharField("Срок", max_length=120, blank=True)
    note = models.CharField(
        "Примечание",
        max_length=200,
        blank=True,
        help_text="Например: «до портов Ванино и Советская Гавань».",
    )
    is_active = models.BooleanField("Показывать", default=True, db_index=True)

    class Meta:
        verbose_name = "Способ доставки"
        verbose_name_plural = "Доставка"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Department(SortableMixin):
    """Отдел филиала: продажи техники, запчасти, сервис, складское оборудование."""

    code = models.SlugField("Код", max_length=60, unique=True)
    name = models.CharField("Название", max_length=160)

    class Meta:
        verbose_name = "Отдел"
        verbose_name_plural = "Отделы"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Employee(TimeStampedModel, PublishableMixin, SortableMixin):
    """Сотрудник филиала, показываемый на странице контактов."""

    branch = models.ForeignKey(
        Branch, verbose_name="Филиал", on_delete=models.CASCADE, related_name="employees"
    )
    department = models.ForeignKey(
        Department,
        verbose_name="Отдел",
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )
    full_name = models.CharField("ФИО", max_length=160)
    position = models.CharField("Должность", max_length=200)
    email = models.EmailField("E-mail", blank=True)
    photo = models.ImageField("Фото", upload_to="staff/", blank=True, null=True)

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ["sort_order", "full_name"]

    def __str__(self) -> str:
        return self.full_name


class ContactPoint(SortableMixin):
    """Телефон, почта или мессенджер филиала либо сотрудника.

    Отдельная таблица, потому что номера идут с добавочными и по несколько на человека.
    """

    class Kind(models.TextChoices):
        PHONE = "phone", "Телефон"
        MOBILE = "mobile", "Мобильный"
        EMAIL = "email", "E-mail"
        TELEGRAM = "telegram", "Telegram"
        WHATSAPP = "whatsapp", "WhatsApp"

    branch = models.ForeignKey(
        Branch,
        verbose_name="Филиал",
        on_delete=models.CASCADE,
        related_name="contacts",
        null=True,
        blank=True,
    )
    employee = models.ForeignKey(
        Employee,
        verbose_name="Сотрудник",
        on_delete=models.CASCADE,
        related_name="contacts",
        null=True,
        blank=True,
    )
    kind = models.CharField("Тип", max_length=16, choices=Kind.choices)
    value = models.CharField("Значение", max_length=120)
    extension = models.CharField("Добавочный", max_length=16, blank=True)
    label = models.CharField("Подпись", max_length=80, blank=True)

    class Meta:
        verbose_name = "Контакт"
        verbose_name_plural = "Контакты"
        ordering = ["sort_order", "id"]
        constraints = [
            # Контакт принадлежит либо филиалу, либо сотруднику, но не обоим сразу:
            # иначе непонятно, где его показывать.
            models.CheckConstraint(
                name="contactpoint_owner_required",
                condition=(
                    models.Q(branch__isnull=False, employee__isnull=True)
                    | models.Q(branch__isnull=True, employee__isnull=False)
                ),
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()}: {self.value}"

    @property
    def display_value(self) -> str:
        """Значение с добавочным, готовое к выводу."""
        if self.extension:
            return f"{self.value} доб. {self.extension}"
        return self.value
