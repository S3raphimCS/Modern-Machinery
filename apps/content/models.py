"""Контентные сущности: страницы, новости, вакансии, меню, настройки сайта."""

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from treebeard.mp_tree import MP_Node

from apps.core.models import (
    PublishableMixin,
    SeoMixin,
    SortableMixin,
    TimeStampedModel,
)


class Page(MP_Node, SeoMixin, PublishableMixin, TimeStampedModel):
    """Статическая страница: О компании, Учебный центр, Охрана труда."""

    slug = models.SlugField("Slug", max_length=140)
    # Полный URL страницы хранится готовым: разбирать дерево на каждый запрос
    # дороже, чем поддерживать одно поле при сохранении.
    #
    # Поле называется `url_path`, а не `path`, потому что `path` уже занято
    # treebeard под материализованный путь дерева. Своё поле с таким именем
    # молча вытесняет служебное, и дерево перестаёт работать — Django на это
    # не ругается.
    url_path = models.CharField("Путь", max_length=255, unique=True, editable=False)
    title = models.CharField("Заголовок", max_length=255)
    menu_title = models.CharField("Заголовок в меню", max_length=120, blank=True)
    template = models.CharField("Шаблон", max_length=100, default="pages/default.html")
    body = models.TextField("Текст", blank=True)

    node_order_by = ["title"]

    class Meta:
        verbose_name = "Страница"
        verbose_name_plural = "Страницы"

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        # Путь пересчитывается при каждом сохранении: слаг предка мог измениться.
        super().save(*args, **kwargs)
        url_path = self.build_url_path()
        if url_path != self.url_path:
            Page.objects.filter(pk=self.pk).update(url_path=url_path)
            self.url_path = url_path

    def build_url_path(self) -> str:
        """Собирает URL страницы из слагов всех предков."""
        # Обход дерева идёт через менеджер: одноимённые методы на самом узле
        # объявлены устаревшими в treebeard 7 и будут удалены в 8-й версии.
        ancestors = Page.objects.get_ancestors(self)
        parts = [ancestor.slug for ancestor in ancestors] + [self.slug]
        return "/" + "/".join(parts) + "/"

    def get_absolute_url(self) -> str:
        return self.url_path


class PageBlock(SortableMixin):
    """Блок конструктора страницы: текст, галерея, преимущества, баннер, CTA."""

    page = models.ForeignKey(
        Page, verbose_name="Страница", on_delete=models.CASCADE, related_name="blocks"
    )
    block_type = models.CharField("Тип блока", max_length=40)
    payload = models.JSONField("Содержимое", default=dict)

    class Meta:
        verbose_name = "Блок страницы"
        verbose_name_plural = "Блоки страниц"
        ordering = ["sort_order"]

    def __str__(self) -> str:
        return f"{self.block_type} #{self.pk}"


class NewsCategory(models.Model):
    slug = models.SlugField("Slug", max_length=100, unique=True)
    name = models.CharField("Название", max_length=120)

    class Meta:
        verbose_name = "Рубрика новостей"
        verbose_name_plural = "Рубрики новостей"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class NewsQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(is_published=True)


class NewsPost(TimeStampedModel, SeoMixin, PublishableMixin):
    slug = models.SlugField("Slug", max_length=180, unique=True)
    title = models.CharField("Заголовок", max_length=255)
    excerpt = models.TextField("Анонс", blank=True)
    body = models.TextField("Текст")
    cover = models.ImageField("Обложка", upload_to="news/%Y/%m/", blank=True, null=True)
    categories = models.ManyToManyField(
        NewsCategory, verbose_name="Рубрики", blank=True, related_name="posts"
    )
    machines = models.ManyToManyField(
        "catalog.Machine", verbose_name="Техника", blank=True, related_name="news"
    )

    objects = NewsQuerySet.as_manager()

    class Meta:
        verbose_name = "Новость"
        verbose_name_plural = "Новости"
        ordering = ["-published_at", "-created_at"]
        indexes = [models.Index(fields=["-published_at", "is_published"], name="news_feed_idx")]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("content:news-detail", kwargs={"slug": self.slug})


class Review(TimeStampedModel, PublishableMixin, SortableMixin):
    """Отзыв клиента, собранный менеджером.

    Публичной формы нет намеренно: в B2B отзывы собирают при разговоре, а
    открытая форма принесла бы спам и чужие персональные данные, которые
    пришлось бы хранить и обезличивать.

    Отзыв можно привязать к модели техники или услуге — тогда он показывается
    на соответствующей карточке. Только там ставится микроразметка: отзыв о
    товаре размечать можно, отзыв организации о самой себе — нет.
    """

    author_name = models.CharField("Имя", max_length=160)
    author_position = models.CharField("Должность", max_length=160, blank=True)
    company = models.CharField("Компания", max_length=200, blank=True)
    city = models.CharField("Город", max_length=120, blank=True)

    rating = models.PositiveSmallIntegerField(
        "Оценка",
        choices=[(value, "★" * value) for value in range(1, 6)],
        default=5,
    )
    text = models.TextField("Текст отзыва")

    machine = models.ForeignKey(
        "catalog.Machine",
        verbose_name="Техника",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )
    service = models.ForeignKey(
        "services.Service",
        verbose_name="Услуга",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )
    source_note = models.CharField(
        "Откуда отзыв",
        max_length=120,
        blank=True,
        help_text="Например: «перенесён из 2ГИС с разрешения автора».",
    )

    objects = NewsQuerySet.as_manager()

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ["-published_at", "sort_order"]
        constraints = [
            models.CheckConstraint(
                name="review_rating_in_range",
                condition=models.Q(rating__gte=1, rating__lte=5),
            )
        ]

    def __str__(self) -> str:
        return f"{self.author_name} — {self.rating}★"

    @property
    def signature(self) -> str:
        """Подпись под отзывом: должность, компания, город."""
        parts = [self.author_position, self.company, self.city]
        return ", ".join(part for part in parts if part)


class ReviewSource(SortableMixin):
    """Рейтинг компании на внешней площадке.

    Показывается ссылкой на источник, без переноса текстов: копировать чужие
    отзывы нельзя, а переносить их оценки в свою микроразметку прямо
    запрещено правилами поисковиков.

    Заполняется вручную: 2ГИС и Google не отдают отзывы через публичный API,
    а меняется такое раз в квартал.
    """

    class Platform(models.TextChoices):
        YANDEX = "yandex", "Яндекс Карты"
        GIS = "2gis", "2ГИС"
        GOOGLE = "google", "Google"

    platform = models.CharField("Площадка", max_length=16, choices=Platform.choices, unique=True)
    rating = models.DecimalField(
        "Рейтинг",
        max_digits=2,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Для Google не заполняется: его оценку переносить на свой сайт нельзя.",
    )
    reviews_count = models.PositiveIntegerField("Число оценок", default=0, blank=True)
    url = models.URLField("Ссылка на карточку")
    widget_code = models.TextField(
        "Код виджета",
        blank=True,
        help_text="Только для Яндекса: код виджета отзывов из Яндекс Карт. "
        "Он подтягивает отзывы сам и обновляет их каждые 72 часа.",
    )
    is_active = models.BooleanField("Показывать", default=True, db_index=True)
    updated_at = models.DateField("Данные на", auto_now=True)

    class Meta:
        verbose_name = "Рейтинг на площадке"
        verbose_name_plural = "Рейтинги на площадках"
        ordering = ["sort_order", "platform"]
        constraints = [
            models.CheckConstraint(
                name="reviewsource_rating_in_range",
                condition=models.Q(rating__isnull=True) | models.Q(rating__gte=0, rating__lte=5),
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_platform_display()}: {self.rating or 'без оценки'}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Проверяет оценку и код виджета.

        Оценку Google переносить на свой сайт нельзя: его правила запрещают
        показывать её за пределами своих продуктов. Карточка остаётся, но
        только ссылкой, поэтому поле блокируется здесь, а не в шаблоне —
        иначе заполнивший его в админке решил бы, что цифра появится.
        """
        if self.platform == self.Platform.GOOGLE and (self.rating or self.reviews_count):
            raise ValidationError(
                {
                    "rating": "Оценку и число отзывов Google показывать нельзя — "
                    "оставьте поля пустыми, на странице будет только ссылка."
                }
            )
        self._check_widget_code()

    def _check_widget_code(self) -> None:
        """Проверяет, что в поле виджета именно виджет Яндекса.

        Содержимое выводится на публичной странице без экранирования, иначе
        `iframe` не отрисуется. Политика безопасности сейчас не даст выполнить
        подставленный скрипт, но полагаться на неё одну нельзя: любое её
        ослабление превратило бы это поле в уязвимость.
        """
        code = (self.widget_code or "").strip()
        if not code:
            return

        allowed_start = "<iframe"
        allowed_src = "https://yandex.ru/maps-reviews-widget/"
        if not code.startswith(allowed_start) or allowed_src not in code:
            raise ValidationError(
                {
                    "widget_code": "Ожидается код виджета отзывов Яндекс Карт: "
                    f"тег iframe со ссылкой на {allowed_src}"
                }
            )
        if "<script" in code.lower() or "javascript:" in code.lower():
            raise ValidationError({"widget_code": "Скрипты в коде виджета запрещены."})


class Vacancy(TimeStampedModel, SeoMixin, PublishableMixin):
    slug = models.SlugField("Slug", max_length=180, unique=True)
    title = models.CharField("Должность", max_length=255)
    branch = models.ForeignKey(
        "company.Branch", verbose_name="Филиал", on_delete=models.PROTECT, related_name="vacancies"
    )
    department = models.ForeignKey(
        "company.Department",
        verbose_name="Отдел",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vacancies",
    )
    description = models.TextField("Описание")
    requirements = models.TextField("Требования", blank=True)
    salary_note = models.CharField("Зарплата", max_length=160, blank=True)

    objects = NewsQuerySet.as_manager()

    class Meta:
        verbose_name = "Вакансия"
        verbose_name_plural = "Вакансии"
        ordering = ["-published_at", "title"]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("content:vacancy-detail", kwargs={"slug": self.slug})


class MenuItem(MP_Node):
    """Редактируемое меню.

    На старом сайте меню засорено пунктами-заглушками (`-`, `--`,
    `javascript:void(0)`). Редактируемая структура позволяет навести порядок
    без правки шаблонов.
    """

    class Location(models.TextChoices):
        HEADER = "header", "Верхнее меню"
        FOOTER = "footer", "Подвал"
        MOBILE = "mobile", "Мобильное меню"

    location = models.CharField("Расположение", max_length=16, choices=Location.choices)
    title = models.CharField("Название", max_length=120)
    page = models.ForeignKey(
        Page, verbose_name="Страница", on_delete=models.SET_NULL, null=True, blank=True
    )
    url = models.CharField("Ссылка", max_length=255, blank=True)
    is_visible = models.BooleanField("Показывать", default=True)
    open_in_new = models.BooleanField("Открывать в новой вкладке", default=False)

    node_order_by = ["title"]

    class Meta:
        verbose_name = "Пункт меню"
        verbose_name_plural = "Меню"

    def __str__(self) -> str:
        return self.title

    @property
    def href(self) -> str:
        if self.page_id:
            return self.page.url_path
        return self.url or "#"


class SiteSettings(models.Model):
    """Синглтон с общими настройками сайта."""

    main_phone = models.CharField("Основной телефон", max_length=40, blank=True)
    main_email = models.EmailField("Основная почта", blank=True)
    address = models.CharField("Адрес", max_length=255, blank=True)
    work_hours = models.CharField("График работы", max_length=255, blank=True)
    metrika_id = models.CharField("ID Яндекс.Метрики", max_length=20, blank=True)
    verification_meta = models.TextField("Мета-теги верификации", blank=True)
    socials = models.JSONField("Соцсети", default=dict, blank=True)
    footer_text = models.TextField("Текст в подвале", blank=True)
    privacy_page = models.ForeignKey(
        Page,
        verbose_name="Политика конфиденциальности",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self) -> str:
        return "Настройки сайта"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        # Синглтон: вторая запись сделала бы поведение сайта зависящим от того,
        # какую из них выберет запрос.
        if not self.pk and SiteSettings.objects.exists():
            raise ValidationError("Настройки сайта уже созданы — отредактируйте существующие.")

    @classmethod
    def load(cls) -> "SiteSettings":
        """Отдаёт настройки, создавая их при первом обращении.

        Создание идёт одним запросом: на пустой таблице параллельные обращения
        иначе создали бы вторую запись, и проверка синглтона уронила бы
        страницу ошибкой сервера.
        """
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
