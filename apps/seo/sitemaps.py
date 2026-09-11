"""Карты сайта.

Отдаются по `/sitemap.xml`; региональные посадочные страницы для филиала важнее
объёма, поэтому в карту попадает только опубликованный и не закрытый от
индексации контент.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        return ["catalog:machine-list", "parts:part-list", "services:service-list"]

    def location(self, item):
        return reverse(item)


class MachineSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9
    protocol = "https"

    def items(self):
        from apps.catalog.models import Machine

        return Machine.objects.visible().filter(is_noindex=False).order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at


class CatalogLandingSitemap(Sitemap):
    """Посадочные подборки каталога.

    Ради них и затевалась региональная семантика: «экскаваторы Komatsu
    Хабаровск» — низкочастотный запрос с высокой конверсией.
    """

    changefreq = "weekly"
    priority = 0.9
    protocol = "https"

    def items(self):
        from apps.catalog.models import CatalogLanding

        return CatalogLanding.objects.filter(is_published=True, is_noindex=False).order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at


class ServiceSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8
    protocol = "https"

    def items(self):
        from apps.services.models import Service

        return Service.objects.visible().filter(is_noindex=False).order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at


class NewsSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.5
    protocol = "https"

    def items(self):
        from apps.content.models import NewsPost

        return NewsPost.objects.visible().filter(is_noindex=False).order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at


class PartSitemap(Sitemap):
    """Карточки запчастей.

    Артикул — самостоятельный поисковый запрос: снабженец ищет «600-311-3750»
    напрямую. Без этих страниц в карте сайта теряются сотни посадочных с
    точным вхождением запроса.
    """

    changefreq = "weekly"
    priority = 0.6
    protocol = "https"
    limit = 5000

    def items(self):
        from apps.parts.models import Part

        return Part.objects.visible().order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at


class PageSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6
    protocol = "https"

    def items(self):
        from apps.content.models import Page

        return Page.objects.filter(is_published=True, is_noindex=False).order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {
    "static": StaticViewSitemap,
    "machines": MachineSitemap,
    "landings": CatalogLandingSitemap,
    "parts": PartSitemap,
    "services": ServiceSitemap,
    "news": NewsSitemap,
    "pages": PageSitemap,
}
