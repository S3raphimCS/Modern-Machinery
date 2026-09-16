"""Заявки с сайта, согласия на обработку ПДн и маршрутизация по отделам."""

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.fields import URLField
from apps.leads.storage import attachment_upload_to, private_storage
from apps.leads.validators import LeadFileValidator


class ConsentVersion(models.Model):
    """Версия текста согласия на обработку персональных данных.

    Версионирование нужно, чтобы через год доказать, с каким именно текстом
    согласился конкретный посетитель. На юридическом согласовании это первый
    вопрос.
    """

    code = models.SlugField("Код", max_length=60)
    version = models.CharField("Версия", max_length=20)
    text = models.TextField("Текст согласия")
    published_at = models.DateTimeField("Опубликовано")
    is_active = models.BooleanField("Действующая", default=True)

    class Meta:
        verbose_name = "Версия согласия"
        verbose_name_plural = "Версии согласия на обработку ПДн"
        ordering = ["-published_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["code", "version"], name="consentversion_unique_version"
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} v{self.version}"

    @classmethod
    def current(cls, code: str = "lead-form") -> "ConsentVersion | None":
        """Действующая версия согласия для формы."""
        return cls.objects.filter(code=code, is_active=True).order_by("-published_at").first()


class Lead(models.Model):
    """Заявка с сайта."""

    class Type(models.TextChoices):
        PRICE = "price", "Запрос цены"
        SELECTION = "selection", "Подбор техники"
        SERVICE = "service", "Заявка в сервис"
        PARTS = "parts", "Запрос запчастей"
        CALLBACK = "callback", "Обратный звонок"
        TCO = "tco", "Калькулятор стоимости владения"
        LEASING = "leasing", "Заявка на лизинг"
        VACANCY = "vacancy", "Отклик на вакансию"

    class Status(models.TextChoices):
        NEW = "new", "Новая"
        IN_PROGRESS = "in_progress", "В работе"
        DONE = "done", "Обработана"
        SPAM = "spam", "Спам"

    type = models.CharField("Тип", max_length=20, choices=Type.choices, db_index=True)
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )

    name = models.CharField("Имя", max_length=160)
    company = models.CharField("Компания", max_length=200, blank=True)
    inn = models.CharField("ИНН", max_length=12, blank=True)
    phone = models.CharField("Телефон", max_length=40, blank=True)
    email = models.EmailField("E-mail", blank=True)
    message = models.TextField("Сообщение", blank=True)

    # Все привязки — SET_NULL: удаление карточки техники не должно уносить
    # с собой заявку, которая по ней пришла.
    machine = models.ForeignKey(
        "catalog.Machine",
        verbose_name="Техника",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    part = models.ForeignKey(
        "parts.Part",
        verbose_name="Запчасть",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    service = models.ForeignKey(
        "services.Service",
        verbose_name="Услуга",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    branch = models.ForeignKey(
        "company.Branch",
        verbose_name="Филиал",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    # Отдел определяет, кому уходит письмо. Заявка, ушедшая не туда, теряется.
    department = models.ForeignKey(
        "company.Department",
        verbose_name="Отдел",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )

    payload = models.JSONField("Дополнительные данные", default=dict, blank=True)
    source_url = URLField("Страница отправки", max_length=500, blank=True)
    referrer = URLField("Источник перехода", max_length=500, blank=True)
    utm = models.JSONField("UTM-метки", default=dict, blank=True)
    ip_address = models.GenericIPAddressField("IP-адрес", null=True, blank=True)
    user_agent = models.CharField("User-Agent", max_length=512, blank=True)

    consent = models.ForeignKey(
        ConsentVersion,
        verbose_name="Согласие",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="leads",
    )
    consent_at = models.DateTimeField("Дата согласия", null=True, blank=True)
    # Срок хранения ПДн: после этой даты заявка обезличивается фоновой задачей.
    purge_after = models.DateField("Хранить до", null=True, blank=True, db_index=True)
    is_anonymized = models.BooleanField("Обезличена", default=False)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Ответственный",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    processed_at = models.DateTimeField("Обработана", null=True, blank=True)

    created_at = models.DateTimeField("Создана", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Изменена", auto_now=True)

    class Meta:
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"], name="lead_status_idx")]

    def __str__(self) -> str:
        return f"{self.get_type_display()} — {self.name or 'обезличена'}"

    @property
    def subject_title(self) -> str:
        """Предмет заявки для темы письма и списка в админке."""
        if self.machine_id:
            return str(self.machine)
        if self.part_id:
            return str(self.part)
        if self.service_id:
            return str(self.service)
        return self.get_type_display()


class LeadAttachment(models.Model):
    """Файл, приложенный к заявке.

    Снабженец присылает спецификацию, техническое задание или список
    артикулов в Excel. Отдельная модель, а не поле у заявки: файлов бывает
    несколько, и ограничение на их число живёт в форме, а не в схеме.
    """

    lead = models.ForeignKey(
        Lead, verbose_name="Заявка", on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(
        "Файл",
        upload_to=attachment_upload_to,
        storage=private_storage,
        validators=[LeadFileValidator()],
    )
    # Имя, под которым файл прислал посетитель. На диске не используется:
    # оно от постороннего и может содержать что угодно.
    original_name = models.CharField("Исходное имя", max_length=255)
    size = models.PositiveIntegerField("Размер, байт", default=0)
    created_at = models.DateTimeField("Загружен", auto_now_add=True)

    class Meta:
        verbose_name = "Вложение"
        verbose_name_plural = "Вложения"
        ordering = ["id"]

    def __str__(self) -> str:
        return self.original_name

    # Файл с диска удаляет сигнал post_delete: он срабатывает и при удалении
    # заявки целиком, когда метод самого объекта Django не вызывает.

    @property
    def display_size(self) -> str:
        """Размер в удобочитаемом виде."""
        if self.size < 1024:
            return f"{self.size} Б"
        if self.size < 1024 * 1024:
            return f"{self.size / 1024:.0f} КБ"
        return f"{self.size / 1024 / 1024:.1f} МБ"


class LeadEvent(models.Model):
    """Событие в жизни заявки: смена статуса, комментарий, отправка письма."""

    class Kind(models.TextChoices):
        CREATED = "created", "Создана"
        STATUS_CHANGED = "status_changed", "Статус изменён"
        COMMENT = "comment", "Комментарий"
        EMAIL_SENT = "email_sent", "Письмо отправлено"
        EMAIL_FAILED = "email_failed", "Письмо не отправлено"
        ANONYMIZED = "anonymized", "Обезличена"

    lead = models.ForeignKey(
        Lead, verbose_name="Заявка", on_delete=models.CASCADE, related_name="events"
    )
    kind = models.CharField("Событие", max_length=40, choices=Kind.choices)
    comment = models.TextField("Комментарий", blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Автор",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField("Когда", auto_now_add=True)

    class Meta:
        verbose_name = "Событие заявки"
        verbose_name_plural = "События заявок"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} — заявка #{self.lead_id}"


class LeadRoutingRule(models.Model):
    """Правило маршрутизации заявки в отдел.

    Внутри филиала техника, запчасти, сервис и складское оборудование — разные
    люди с разными адресами. Правила редактируются в админке, чтобы менеджер мог
    поменять адрес без разработчика.
    """

    name = models.CharField("Название", max_length=160)
    lead_type = models.CharField(
        "Тип заявки",
        max_length=20,
        choices=Lead.Type.choices,
        blank=True,
        help_text="Пусто — правило подходит для любого типа заявки.",
    )
    category = models.ForeignKey(
        "catalog.Category",
        verbose_name="Категория техники",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="routing_rules",
    )
    machine_type = models.ForeignKey(
        "catalog.MachineType",
        verbose_name="Тип техники",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="routing_rules",
    )
    department = models.ForeignKey(
        "company.Department",
        verbose_name="Отдел",
        on_delete=models.PROTECT,
        related_name="routing_rules",
    )
    emails = ArrayField(models.EmailField(), verbose_name="Адреса", default=list)
    # Меньше значение — выше приоритет. Первое подошедшее правило выигрывает.
    priority = models.PositiveSmallIntegerField("Приоритет", default=100)
    is_active = models.BooleanField("Активно", default=True, db_index=True)

    class Meta:
        verbose_name = "Правило маршрутизации"
        verbose_name_plural = "Правила маршрутизации заявок"
        ordering = ["priority", "id"]

    def __str__(self) -> str:
        return self.name


# Модульная константа нужна drf-spectacular: он резолвит переопределения имён
# enum по пути к переменной модуля, а не к вложенному классу.
LEAD_STATUS_CHOICES = Lead.Status.choices
