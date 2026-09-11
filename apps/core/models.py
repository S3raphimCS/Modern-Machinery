"""Абстрактные базовые модели, общие для всего проекта."""

from django.db import models


class TimeStampedModel(models.Model):
    """Отметки создания и изменения записи."""

    created_at = models.DateTimeField("Создано", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Изменено", auto_now=True)

    class Meta:
        abstract = True


class SeoMixin(models.Model):
    """SEO-поля публичной страницы.

    Наследуется всеми сущностями, у которых есть собственный URL: снимает вечный
    вопрос «а как задать title для этой страницы».
    """

    seo_title = models.CharField("SEO: title", max_length=255, blank=True)
    seo_description = models.TextField("SEO: description", blank=True)
    seo_h1 = models.CharField("SEO: H1", max_length=255, blank=True)
    og_image = models.ImageField("Картинка для соцсетей", upload_to="og/", blank=True, null=True)
    is_noindex = models.BooleanField("Закрыть от индексации", default=False)

    class Meta:
        abstract = True


class PublishableMixin(models.Model):
    """Черновик и публикация вместо физического удаления."""

    is_published = models.BooleanField("Опубликовано", default=False, db_index=True)
    published_at = models.DateTimeField("Дата публикации", null=True, blank=True)

    class Meta:
        abstract = True


class SortableMixin(models.Model):
    """Ручной порядок вывода в списках."""

    sort_order = models.PositiveSmallIntegerField("Порядок", default=100)

    class Meta:
        abstract = True
