"""Тесты посадочных подборок каталога и правил индексации."""

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.catalog.factories import MachineFactory, MachineTypeFactory
from apps.catalog.models import CatalogLanding

pytestmark = pytest.mark.django_db


@pytest.fixture
def landing(brand, machine_type):
    return CatalogLanding.objects.create(
        slug="ekskavatory-komatsu-habarovsk",
        title="Экскаваторы Komatsu в Хабаровске",
        intro="Уникальный текст подборки под региональный запрос.",
        brand=brand,
        machine_type=machine_type,
        is_published=True,
    )


def test_landing_page_renders(client, landing, machine):
    response = client.get(landing.get_absolute_url())

    assert response.status_code == 200
    assert response.context["landing"] == landing
    assert "Экскаваторы Komatsu в Хабаровске" in response.content.decode()


def test_landing_applies_its_conditions(client, landing, brand, machine_type):
    """Подборка показывает только подходящую технику, а не весь каталог."""
    MachineFactory(slug="matching", brand=brand, machine_type=machine_type)
    MachineFactory(slug="other-type", brand=brand, machine_type=MachineTypeFactory(slug="kran"))

    assert client.get(landing.get_absolute_url()).context["total"] == 1


def test_landing_conditions_win_over_query_params(client, landing, brand, machine_type):
    """Подменить условия подборки через адрес нельзя.

    Иначе одна и та же страница отдавала бы разный товар по одному URL, и
    поисковик получил бы нестабильное содержимое.
    """
    MachineFactory(slug="matching", brand=brand, machine_type=machine_type)
    other = MachineTypeFactory(slug="kran")
    MachineFactory(slug="crane", brand=brand, machine_type=other)

    response = client.get(landing.get_absolute_url(), {"type": other.slug})
    assert response.context["total"] == 1


def test_landing_is_indexable_and_canonical(client, landing, machine):
    content = client.get(landing.get_absolute_url()).content.decode()

    assert f'<link rel="canonical" href="http://testserver{landing.get_absolute_url()}">' in content
    assert "noindex" not in content


def test_landing_with_extra_filters_is_not_indexed(client, landing, machine):
    """Подборка плюс сторонний фильтр — уже не самостоятельная страница."""
    content = client.get(landing.get_absolute_url(), {"in_stock": "1"}).content.decode()

    assert 'content="noindex,follow"' in content
    # Канонический адрес по-прежнему ведёт на саму подборку.
    assert f'href="http://testserver{landing.get_absolute_url()}"' in content


def test_unpublished_landing_returns_404(client, landing):
    landing.is_published = False
    landing.save()
    assert client.get(landing.get_absolute_url()).status_code == 404


def test_landing_requires_at_least_one_condition():
    """Подборка без условий дублировала бы каталог целиком."""
    with pytest.raises(IntegrityError), transaction.atomic():
        CatalogLanding.objects.create(slug="pustaya", title="Пустая подборка")


def test_catalog_links_to_landings(client, landing, machine):
    content = client.get(reverse("catalog:machine-list")).content.decode()

    assert landing.get_absolute_url() in content
    assert "Популярные подборки" in content


def test_landing_does_not_link_to_itself(client, landing, machine):
    content = client.get(landing.get_absolute_url()).content.decode()
    assert content.count(f'href="{landing.get_absolute_url()}"') == 0


def test_hidden_landing_not_linked(client, landing, machine):
    landing.is_featured = False
    landing.save()
    assert "Популярные подборки" not in client.get(reverse("catalog:machine-list")).content.decode()


def test_catalog_without_filters_is_indexable(client, machine):
    content = client.get(reverse("catalog:machine-list")).content.decode()

    assert "noindex" not in content
    assert '<link rel="canonical" href="http://testserver/">' in content


def test_filtered_catalog_is_not_indexed(client, machine, brand):
    """Сочетаний фильтров тысячи — в индексе им делать нечего."""
    content = client.get(reverse("catalog:machine-list"), {"brand": brand.slug}).content.decode()

    assert 'content="noindex,follow"' in content
    assert '<link rel="canonical" href="http://testserver/">' in content


def test_search_results_are_not_indexed(client, machine):
    content = client.get(reverse("catalog:machine-list"), {"q": "PC400"}).content.decode()
    assert 'content="noindex,follow"' in content


def test_landing_str_and_url(landing):
    assert str(landing) == "Экскаваторы Komatsu в Хабаровске"
    assert landing.get_absolute_url() == "/katalog/ekskavatory-komatsu-habarovsk/"


@pytest.fixture
def weight_key(spec_group):
    from apps.specs.factories import SpecKeyFactory
    from apps.specs.models import SpecKey

    return SpecKeyFactory(
        code="operating_weight",
        name="Эксплуатационная масса",
        group=spec_group,
        unit="кг",
        value_type=SpecKey.ValueType.NUMBER,
        is_filterable=True,
    )


def make_range_landing(machine_type, weight_key, low=20000, high=25000):
    from apps.catalog.models import CatalogLandingSpec

    landing = CatalogLanding.objects.create(
        slug="ekskavatory-20-25-tonn",
        title="Экскаваторы 20–25 тонн",
        machine_type=machine_type,
        is_published=True,
    )
    CatalogLandingSpec.objects.create(
        landing=landing, spec_key=weight_key, value_min=low, value_max=high
    )
    return landing


def machine_with_weight(brand, machine_type, weight_key, slug, weight):
    from apps.specs.models import MachineSpec

    machine = MachineFactory(slug=slug, brand=brand, machine_type=machine_type)
    MachineSpec.objects.create(machine=machine, spec_key=weight_key, value_num=weight)
    return machine


def test_range_landing_filters_by_specification(client, brand, machine_type, weight_key):
    """Страница под запрос «экскаватор 20 тонн» отбирает технику по массе."""
    machine_with_weight(brand, machine_type, weight_key, "light", 15000)
    machine_with_weight(brand, machine_type, weight_key, "match", 22000)
    machine_with_weight(brand, machine_type, weight_key, "heavy", 30000)

    landing = make_range_landing(machine_type, weight_key)
    response = client.get(landing.get_absolute_url())

    assert response.context["total"] == 1


def test_open_ended_range_works(client, brand, machine_type, weight_key):
    """Подборка «от 30 тонн» задаётся только нижней границей."""
    machine_with_weight(brand, machine_type, weight_key, "light", 15000)
    machine_with_weight(brand, machine_type, weight_key, "heavy", 35000)

    landing = make_range_landing(machine_type, weight_key, low=30000, high=None)

    assert client.get(landing.get_absolute_url()).context["total"] == 1


def test_range_landing_stays_indexable(client, brand, machine_type, weight_key):
    """Диапазон — условие самой подборки, а не посторонний фильтр.

    Без учёта диапазонов в подсчёте условий такая страница считалась бы
    отфильтрованной и уходила в noindex — то есть в поиск бы не попала.
    """
    machine_with_weight(brand, machine_type, weight_key, "match", 22000)
    landing = make_range_landing(machine_type, weight_key)

    content = client.get(landing.get_absolute_url()).content.decode()

    assert "noindex" not in content
    assert f'<link rel="canonical" href="http://testserver{landing.get_absolute_url()}">' in content


def test_extra_filter_on_range_landing_is_not_indexed(client, brand, machine_type, weight_key):
    machine_with_weight(brand, machine_type, weight_key, "match", 22000)
    landing = make_range_landing(machine_type, weight_key)

    content = client.get(landing.get_absolute_url(), {"in_stock": "1"}).content.decode()

    assert 'content="noindex,follow"' in content


def test_landing_range_wins_over_query_params(client, brand, machine_type, weight_key):
    """Подменить диапазон через адрес нельзя: страница обязана быть стабильной."""
    machine_with_weight(brand, machine_type, weight_key, "light", 15000)
    machine_with_weight(brand, machine_type, weight_key, "match", 22000)
    landing = make_range_landing(machine_type, weight_key)

    response = client.get(landing.get_absolute_url(), {"spec_operating_weight_min": "10000"})

    assert response.context["total"] == 1


def test_condition_requires_at_least_one_bound(machine_type, weight_key):
    from django.db import IntegrityError, transaction

    from apps.catalog.models import CatalogLandingSpec

    landing = CatalogLanding.objects.create(
        slug="bez-granic", title="Без границ", machine_type=machine_type, is_published=True
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        CatalogLandingSpec.objects.create(landing=landing, spec_key=weight_key)


def test_reversed_bounds_rejected(machine_type, weight_key):
    from django.db import IntegrityError, transaction

    from apps.catalog.models import CatalogLandingSpec

    landing = CatalogLanding.objects.create(
        slug="perevernutyy",
        title="Перевёрнутый",
        machine_type=machine_type,
        is_published=True,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        CatalogLandingSpec.objects.create(
            landing=landing, spec_key=weight_key, value_min=30000, value_max=10000
        )


def test_one_condition_per_parameter(machine_type, weight_key):
    from django.db import IntegrityError, transaction

    from apps.catalog.models import CatalogLandingSpec

    landing = make_range_landing(machine_type, weight_key)

    with pytest.raises(IntegrityError), transaction.atomic():
        CatalogLandingSpec.objects.create(
            landing=landing, spec_key=weight_key, value_min=1, value_max=2
        )


def test_condition_str_covers_all_shapes(machine_type, weight_key):
    from apps.catalog.models import CatalogLandingSpec

    landing = CatalogLanding.objects.create(
        slug="vidy", title="Виды", machine_type=machine_type, is_published=True
    )
    both = CatalogLandingSpec(landing=landing, spec_key=weight_key, value_min=1, value_max=2)
    only_low = CatalogLandingSpec(landing=landing, spec_key=weight_key, value_min=1)
    only_high = CatalogLandingSpec(landing=landing, spec_key=weight_key, value_max=2)

    assert "1–2" in str(both)
    assert str(only_low).endswith("от 1")
    assert str(only_high).endswith("до 2")
