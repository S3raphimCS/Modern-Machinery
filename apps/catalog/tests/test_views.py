"""Тесты страниц каталога, включая частичное обновление через HTMX."""

import pytest
from django.urls import reverse

from apps.catalog.factories import MachineFactory
from apps.catalog.signals import rebuild_search_vector

pytestmark = pytest.mark.django_db


def test_catalog_page_renders(client, machine_factory_set):
    response = client.get(reverse("catalog:machine-list"))
    assert response.status_code == 200
    assert response.context["total"] == 3
    assert "catalog/machine_list.html" in [t.name for t in response.templates]


def test_catalog_applies_filters_from_query(client, machine_factory_set, power_key):
    response = client.get(reverse("catalog:machine-list"), {"spec_engine_power_min": "300"})
    assert response.context["total"] == 1


def test_htmx_request_returns_only_results(client, machine_factory_set):
    """HTMX подменяет список, а не всю страницу — иначе теряется состояние формы."""
    response = client.get(reverse("catalog:machine-list"), HTTP_HX_REQUEST="true")
    names = [t.name for t in response.templates]

    assert "catalog/partials/machine_grid.html" in names
    assert "base.html" not in names


def test_pagination_querystring_drops_page(client, machine_factory_set, brand):
    response = client.get(reverse("catalog:machine-list"), {"brand": brand.slug, "page": "1"})
    assert "page=" not in response.context["querystring"]
    assert f"brand={brand.slug}" in response.context["querystring"]


def test_empty_result_shows_message(client, machine_factory_set, power_key):
    response = client.get(reverse("catalog:machine-list"), {"spec_engine_power_min": "9999"})
    assert response.context["total"] == 0
    assert "не найдена" in response.content.decode()


def test_machine_detail_renders(client, machine, power_key):
    from apps.specs.models import MachineSpec

    MachineSpec.objects.create(machine=machine, spec_key=power_key, value_num=257)
    response = client.get(machine.get_absolute_url())

    assert response.status_code == 200
    assert "Двигатель" in response.context["spec_groups"]
    assert response.context["lead_form"] is not None


def test_unpublished_machine_returns_404(client, machine):
    machine.is_published = False
    machine.save()
    assert client.get(machine.get_absolute_url()).status_code == 404


def test_detail_shows_similar_machines(client, machine, brand, machine_type):
    MachineFactory(slug="similar-one", brand=brand, machine_type=machine_type)
    response = client.get(machine.get_absolute_url())
    assert len(response.context["similar_machines"]) == 1


def test_search_suggest_returns_matches(client, machine):
    rebuild_search_vector(machine.pk)
    response = client.get(reverse("catalog:machine-search-suggest"), {"q": "PC400"})
    assert response.status_code == 200
    assert list(response.context["suggestions"]) == [machine]


def test_search_suggest_ignores_short_query(client, machine):
    response = client.get(reverse("catalog:machine-search-suggest"), {"q": "P"})
    assert response.context["suggestions"] == []


def test_tehnika_prefix_redirects_to_root(client):
    """Канонический адрес каталога один, чтобы не плодить дубли для поисковика."""
    response = client.get("/tehnika/")
    assert response.status_code == 301
    assert response["Location"] == "/"


def test_filter_sections_are_collapsed_by_default(client, machine_factory_set, power_key):
    """Каждый раздел фильтров свёрнут по отдельности, сама панель на виду."""
    content = client.get(reverse("catalog:machine-list")).content.decode()

    assert 'mm-filters__head-title">Фильтры<' in content
    assert content.count('<details class="mm-filters__section" >') >= 3
    assert '<details class="mm-filters__section" open>' not in content


def test_section_with_selection_is_expanded(client, machine_factory_set, brand):
    """Раскрывается только тот раздел, в котором уже что-то выбрано.

    Иначе посетитель не увидит применённые условия за свёрнутым заголовком.
    """
    content = client.get(reverse("catalog:machine-list"), {"brand": brand.slug}).content.decode()

    assert content.count('<details class="mm-filters__section" open>') == 1
    # Остальные разделы (тип техники и мощность) остались свёрнутыми.
    assert content.count('<details class="mm-filters__section" >') == 2


def test_numeric_section_expands_for_range(client, machine_factory_set, power_key):
    content = client.get(
        reverse("catalog:machine-list"), {"spec_engine_power_min": "200"}
    ).content.decode()

    assert content.count('<details class="mm-filters__section" open>') == 1
    assert "mm-filters__badge--dot" in content


def test_section_headers_show_selection_count(client, machine_factory_set, brand, machine_type):
    content = client.get(
        reverse("catalog:machine-list"), {"brand": brand.slug, "type": machine_type.slug}
    ).content.decode()

    # Два раздела раскрыты, на каждом счётчик выбранных значений.
    assert content.count('<details class="mm-filters__section" open>') == 2
    assert content.count('mm-filters__badge mm-filters__badge--small">1<') == 2


def test_total_badge_counts_all_conditions(client, machine_factory_set, brand):
    content = client.get(
        reverse("catalog:machine-list"), {"brand": brand.slug, "in_stock": "1"}
    ).content.decode()

    assert 'class="mm-filters__badge">2<' in content
    assert "Сбросить фильтры" in content


def test_reset_link_hidden_without_filters(client, machine_factory_set):
    content = client.get(reverse("catalog:machine-list")).content.decode()
    assert "Сбросить фильтры" not in content
