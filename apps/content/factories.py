"""Фабрики контента."""

import factory
from django.utils import timezone

from apps.company.factories import BranchFactory

from .models import NewsPost, Page, Vacancy


class PageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Page
        django_get_or_create = ["slug"]

    slug = factory.Sequence(lambda n: f"page-{n}")
    title = factory.Sequence(lambda n: f"Страница {n}")
    body = "Текст страницы."
    is_published = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        kwargs.setdefault("url_path", f"/{kwargs['slug']}/")
        return model_class.objects.add_root(kwargs)


class NewsPostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NewsPost
        skip_postgeneration_save = True

    slug = factory.Sequence(lambda n: f"news-{n}")
    title = factory.Sequence(lambda n: f"Новость {n}")
    body = "Текст новости."
    is_published = True
    published_at = factory.LazyFunction(timezone.now)


class VacancyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Vacancy

    slug = factory.Sequence(lambda n: f"vacancy-{n}")
    title = factory.Sequence(lambda n: f"Вакансия {n}")
    branch = factory.SubFactory(BranchFactory)
    description = "Описание вакансии."
    is_published = True
    published_at = factory.LazyFunction(timezone.now)
