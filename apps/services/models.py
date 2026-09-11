"""Модуль услуг сервисного центра.

Для филиала сервис — самостоятельный продукт с коротким циклом сделки, а не
приложение к продаже техники. Именно с услуг проще всего получить первые заявки
с сайта, поэтому раздел сделан полноценным модулем, а не строкой в меню.
"""

from django.db import models
from django.urls import reverse

from apps.core.models import PublishableMixin, SeoMixin, SortableMixin, TimeStampedModel


class ServiceCategory(SortableMixin):
    """ТО и ремонт, диагностика, анализ масел, выезд на объект, обучение."""

    slug = models.SlugField("Slug", max_length=120, unique=True)
    name = models.CharField("Название", max_length=160)
    icon = models.FileField("Иконка", upload_to="services/", blank=True, null=True)

    class Meta:
        verbose_name = "Категория услуг"
        verbose_name_plural = "Категории услуг"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class ServiceQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(is_published=True)


class Service(TimeStampedModel, SeoMixin, PublishableMixin, SortableMixin):
    """Услуга сервисного центра."""

    slug = models.SlugField("Slug", max_length=160, unique=True)
    name = models.CharField("Название", max_length=200)
    category = models.ForeignKey(
        ServiceCategory, verbose_name="Категория", on_delete=models.PROTECT, related_name="services"
    )
    short_description = models.TextField("Краткое описание", blank=True)
    description = models.TextField("Описание", blank=True)

    price_from = models.DecimalField(
        "Цена от", max_digits=12, decimal_places=2, null=True, blank=True
    )
    price_note = models.CharField("Примечание к цене", max_length=160, blank=True)
    is_on_site = models.BooleanField("Выезд на объект", default=False)
    is_available = models.BooleanField("Доступна сейчас", default=True)
    lead_time = models.CharField("Срок выполнения", max_length=120, blank=True)

    machine_types = models.ManyToManyField(
        "catalog.MachineType", verbose_name="Типы техники", blank=True, related_name="services"
    )
    brands = models.ManyToManyField(
        "catalog.Brand", verbose_name="Бренды", blank=True, related_name="services"
    )

    objects = ServiceQuerySet.as_manager()

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("services:service-detail", kwargs={"slug": self.slug})

    @property
    def display_price(self) -> str:
        if self.price_from is None:
            return "По запросу"
        note = f" {self.price_note}" if self.price_note else ""
        return f"от {self.price_from:,.0f} ₽{note}".replace(",", " ")
