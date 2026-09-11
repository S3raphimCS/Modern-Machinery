"""Тесты SEO-слоя: редиректы, мониторинг 404, robots и карта сайта."""

import pytest

from apps.seo.models import NotFoundLog, RedirectRule

pytestmark = pytest.mark.django_db


def test_redirect_rule_applied(client):
    RedirectRule.objects.create(old_path="/old-catalog/", new_path="/", status_code=301)
    response = client.get("/old-catalog/")

    assert response.status_code == 301
    assert response["Location"] == "/"


def test_temporary_redirect(client):
    RedirectRule.objects.create(old_path="/vremenno/", new_path="/uslugi/", status_code=302)
    assert client.get("/vremenno/").status_code == 302


def test_redirect_counts_hits(client):
    rule = RedirectRule.objects.create(old_path="/staraya/", new_path="/")
    client.get("/staraya/")
    client.get("/staraya/")

    rule.refresh_from_db()
    assert rule.hits == 2
    assert rule.last_hit_at is not None


def test_redirect_matches_path_without_trailing_slash(client):
    """Старые адреса приходят и без завершающего слэша."""
    RedirectRule.objects.create(old_path="/katalog/", new_path="/")
    assert client.get("/katalog").status_code in {301, 302}


def test_inactive_redirect_ignored(client):
    RedirectRule.objects.create(old_path="/otkljucheno/", new_path="/", is_active=False)
    assert client.get("/otkljucheno/").status_code == 404


def test_missing_page_is_logged(client):
    """Первые недели после переезда это главный инструмент поиска потерь."""
    client.get("/net-takoy-stranicy/")
    entry = NotFoundLog.objects.get(path="/net-takoy-stranicy/")
    assert entry.hits == 1


def test_repeated_404_increments_counter(client):
    client.get("/net-takoy/")
    client.get("/net-takoy/")
    assert NotFoundLog.objects.get(path="/net-takoy/").hits == 2


def test_404_log_records_referrer(client):
    client.get("/poteryannaya/", HTTP_REFERER="https://yandex.ru/search")
    assert NotFoundLog.objects.get(path="/poteryannaya/").referrer == "https://yandex.ru/search"


@pytest.mark.parametrize("path", ["/static/css/main.css", "/media/x.jpg", "/favicon.ico"])
def test_service_paths_not_logged(client, path):
    """404 по статике — норма, а не потерянная ссылка."""
    client.get(path)
    assert NotFoundLog.objects.count() == 0


def test_successful_page_not_logged(client, branch):
    client.get("/")
    assert NotFoundLog.objects.count() == 0


def test_redirect_takes_priority_over_logging(client):
    RedirectRule.objects.create(old_path="/perenesena/", new_path="/")
    client.get("/perenesena/")
    assert NotFoundLog.objects.filter(path="/perenesena/").exists() is False


def test_robots_txt(client):
    response = client.get("/robots.txt")
    content = response.content.decode()

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    assert "Disallow: /admin/" in content
    assert "Disallow: /api/" in content
    assert "Sitemap: http://testserver/sitemap.xml" in content
    assert "Host: testserver" in content


def test_sitemap_lists_published_machines(client, machine):
    content = client.get("/sitemap.xml").content.decode()
    assert machine.get_absolute_url() in content


def test_sitemap_excludes_unpublished(client, machine):
    machine.is_published = False
    machine.save()
    assert machine.get_absolute_url() not in client.get("/sitemap.xml").content.decode()


def test_sitemap_excludes_noindex(client, machine):
    """Страница, закрытая от индексации, не должна попадать в карту сайта."""
    machine.is_noindex = True
    machine.save()
    assert machine.get_absolute_url() not in client.get("/sitemap.xml").content.decode()


def test_sitemap_includes_services_news_pages(client, db):
    from apps.content.factories import NewsPostFactory, PageFactory
    from apps.services.factories import ServiceFactory

    service = ServiceFactory(slug="to-komatsu")
    post = NewsPostFactory(slug="novost")
    PageFactory(slug="o-nas")

    content = client.get("/sitemap.xml").content.decode()
    assert service.get_absolute_url() in content
    assert post.get_absolute_url() in content
    assert "/o-nas/" in content


def test_model_str_methods():
    rule = RedirectRule.objects.create(old_path="/a/", new_path="/b/")
    entry = NotFoundLog.objects.create(path="/c/")

    assert str(rule) == "/a/ → /b/"
    assert str(entry) == "/c/ (1)"


def test_sitemap_includes_parts(client, brand):
    """Артикул — самостоятельный поисковый запрос, страница нужна в карте."""
    from apps.parts.factories import PartFactory

    part = PartFactory(brand=brand, article="600-311-3750")
    assert part.get_absolute_url() in client.get("/sitemap.xml").content.decode()


def test_sitemap_includes_landings(client, brand, machine_type):
    from apps.catalog.models import CatalogLanding

    landing = CatalogLanding.objects.create(
        slug="ekskavatory-komatsu",
        title="Экскаваторы Komatsu",
        brand=brand,
        machine_type=machine_type,
        is_published=True,
    )
    assert landing.get_absolute_url() in client.get("/sitemap.xml").content.decode()


def test_sitemap_excludes_noindex_landing(client, brand):
    from apps.catalog.models import CatalogLanding

    landing = CatalogLanding.objects.create(
        slug="skrytaya",
        title="Скрытая подборка",
        brand=brand,
        is_published=True,
        is_noindex=True,
    )
    assert landing.get_absolute_url() not in client.get("/sitemap.xml").content.decode()


def test_sitemap_excludes_unpublished_part(client, brand):
    from apps.parts.factories import PartFactory

    part = PartFactory(brand=brand, is_published=False)
    assert part.get_absolute_url() not in client.get("/sitemap.xml").content.decode()
