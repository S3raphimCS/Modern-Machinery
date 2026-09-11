"""Контентные сущности: страницы, новости, вакансии, меню, настройки сайта."""

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from treebeard.mp_tree import MP_Node

from apps.core.models import PublishableMixin, SeoMixin, SortableMixin, TimeStampedModel


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
        """Отдаёт настройки, создавая их при первом обращении."""
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj
