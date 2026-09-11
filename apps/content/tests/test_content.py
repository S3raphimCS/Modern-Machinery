"""Тесты контентных сущностей и страниц."""

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError

from apps.company.factories import EmployeeFactory
from apps.content.context_processors import site_context
from apps.content.factories import NewsPostFactory, PageFactory, VacancyFactory
from apps.content.models import MenuItem, NewsPost, Page, PageBlock, SiteSettings

pytestmark = pytest.mark.django_db


def test_page_builds_url_path_from_tree():
    """Путь собирается из слагов предков и хранится готовым."""
    root = PageFactory(slug="o-kompanii", title="О компании")
    child = Page.objects.add_child(
        root,
        {"slug": "istoriya", "title": "История", "is_published": True, "url_path": "/placeholder/"},
    )
    child.save()
    child.refresh_from_db()

    assert child.url_path == "/o-kompanii/istoriya/"
    assert child.get_absolute_url() == "/o-kompanii/istoriya/"


def test_page_url_path_is_separate_from_tree_path():
    """Своё поле `path` вытеснило бы служебное поле treebeard и сломало дерево."""
    page = PageFactory(slug="uslovija")
    assert page.url_path == "/uslovija/"
    assert page.path != page.url_path


def test_site_settings_is_singleton():
    SiteSettings.load()
    with pytest.raises(ValidationError):
        SiteSettings(main_phone="+7 000").save()


def test_site_settings_load_creates_once():
    first = SiteSettings.load()
    assert SiteSettings.load().pk == first.pk


def test_menu_item_href_prefers_page():
    page = PageFactory(slug="uchebnyy-centr")
    item = MenuItem.objects.add_root({"location": "header", "title": "Учебный центр", "page": page})
    assert item.href == "/uchebnyy-centr/"


def test_menu_item_href_falls_back_to_url():
    item = MenuItem.objects.add_root(
        {"location": "footer", "title": "Внешняя", "url": "https://example.com"}
    )
    assert item.href == "https://example.com"


def test_menu_item_href_defaults_to_hash():
    item = MenuItem.objects.add_root({"location": "footer", "title": "Заглушка"})
    assert item.href == "#"


def test_context_processor_returns_site_data(rf, branch):
    settings_obj = SiteSettings.load()
    settings_obj.main_phone = "+7 (4212) 45-67-00"
    settings_obj.save()
    MenuItem.objects.add_root({"location": "header", "title": "Техника", "url": "/"})

    context = site_context(rf.get("/"))

    assert context["site_settings"].main_phone == "+7 (4212) 45-67-00"
    assert context["main_branch"] == branch
    assert [item.title for item in context["site_menu"]["header"]] == ["Техника"]
    assert context["callback_form"] is not None


def test_context_processor_uses_cache(rf, branch):
    site_context(rf.get("/"))
    assert cache.get("content:menu:v1") is not None


def test_about_page(client, branch):
    EmployeeFactory(branch=branch, full_name="Гордеев И. Р.")
    response = client.get("/o-kompanii/")

    assert response.status_code == 200
    assert "Гордеев И. Р." in response.content.decode()


def test_about_page_404_without_branch(client, db):
    assert client.get("/o-kompanii/").status_code == 404


def test_news_list_and_detail(client):
    post = NewsPostFactory(title="Новая линейка катков")
    assert client.get("/novosti/").status_code == 200
    assert client.get(post.get_absolute_url()).status_code == 200


def test_unpublished_news_hidden(client):
    post = NewsPostFactory(is_published=False)
    assert NewsPost.objects.visible().count() == 0
    assert client.get(post.get_absolute_url()).status_code == 404


def test_vacancy_list_and_detail(client, branch):
    vacancy = VacancyFactory(branch=branch, title="Сервисный инженер")
    assert client.get("/vakansii/").status_code == 200
    assert client.get(vacancy.get_absolute_url()).status_code == 200


def test_arbitrary_page_renders(client):
    PageFactory(slug="ohrana-truda", title="Охрана труда", body="Текст")
    response = client.get("/ohrana-truda/")

    assert response.status_code == 200
    assert "Охрана труда" in response.content.decode()


def test_page_template_cannot_escape_pages_directory(client):
    """Шаблон задаётся в админке, поэтому путь проверяется на выход за каталог."""
    PageFactory(slug="opasnaya", template="../../../etc/passwd")
    response = client.get("/opasnaya/")

    assert response.status_code == 200
    assert "pages/default.html" in [t.name for t in response.templates]


def test_page_blocks_rendered(client):
    page = PageFactory(slug="s-blokami")
    PageBlock.objects.create(
        page=page, block_type="text", payload={"title": "Заголовок блока", "text": "Текст блока"}
    )

    content = client.get("/s-blokami/").content.decode()
    assert "Заголовок блока" in content
    assert "Текст блока" in content


def test_unpublished_page_404(client):
    PageFactory(slug="chernovik", is_published=False)
    assert client.get("/chernovik/").status_code == 404


def test_privacy_page(client):
    PageFactory(slug="politika-konfidencialnosti", title="Политика", body="Текст политики")
    response = client.get("/politika-konfidencialnosti/")

    assert response.status_code == 200
    assert "Текст политики" in response.content.decode()


def test_privacy_page_without_content(client, branch):
    response = client.get("/politika-konfidencialnosti/")
    assert response.status_code == 200
    assert "152-ФЗ" in response.content.decode()


def test_api_pages_news_vacancies(client, branch):
    PageFactory(slug="o-nas", title="О нас")
    NewsPostFactory(title="Новость")
    VacancyFactory(branch=branch, title="Механик")

    assert client.get("/api/v1/pages/").json()[0]["slug"] == "o-nas"
    assert client.get("/api/v1/news/").json()["results"][0]["title"] == "Новость"
    assert client.get("/api/v1/vacancies/").json()["results"][0]["title"] == "Механик"


def test_api_page_includes_blocks(client):
    page = PageFactory(slug="s-blokom")
    PageBlock.objects.create(page=page, block_type="cta", payload={"title": "Заявка"})

    data = client.get("/api/v1/pages/").json()[0]
    assert data["blocks"] == [{"type": "cta", "payload": {"title": "Заявка"}}]


def test_model_str_methods(branch):
    page = PageFactory(slug="stranica", title="Страница")
    assert str(page) == "Страница"
    assert str(NewsPostFactory(title="Заголовок")) == "Заголовок"
    assert str(VacancyFactory(branch=branch, title="Вакансия")) == "Вакансия"
    assert str(SiteSettings.load()) == "Настройки сайта"
    assert str(PageBlock.objects.create(page=page, block_type="text")).startswith("text")
