"""Тесты фасетов каталога и их кэширования."""

from decimal import Decimal

import pytest
from django.core.cache import cache
from django.http import QueryDict

from apps.catalog.factories import MachineFactory
from apps.catalog.services.facets import (
    _cache_key,
    annotate_selection,
    build_facets,
    get_facets,
    invalidate_facets,
)
from apps.catalog.services.filters import parse_filters
from apps.specs.factories import SpecKeyFactory, SpecOptionFactory
from apps.specs.models import MachineSpec, SpecKey

pytestmark = pytest.mark.django_db


def test_facets_count_brands_and_types(machine_factory_set, brand, machine_type):
    facets = build_facets()
    assert facets["total"] == 3
    assert facets["brands"][0] == {"slug": brand.slug, "name": brand.name, "count": 3}
    assert facets["machine_types"][0]["count"] == 3


def test_numeric_facet_reports_bounds(machine_factory_set, power_key):
    facets = build_facets()
    numeric = next(item for item in facets["numeric"] if item["code"] == "engine_power")
    assert numeric["min"] == 150.0
    assert numeric["max"] == 350.0
    assert numeric["unit"] == "кВт"


def test_numeric_facet_accounts_for_range_upper_bound(machine, spec_group):
    """Верхняя граница шкалы учитывает диапазонные значения."""
    key = SpecKeyFactory(code="digging_depth", group=spec_group, unit="м", decimals=1)
    MachineSpec.objects.create(
        machine=machine,
        spec_key=key,
        value_num=Decimal("6.6"),
        value_num_max=Decimal("7.4"),
    )
    numeric = next(item for item in build_facets()["numeric"] if item["code"] == "digging_depth")
    assert numeric["max"] == 7.4


def test_numeric_facet_skipped_when_no_values(power_key):
    assert build_facets()["numeric"] == []


def test_option_facet_counts_values(brand, machine_type, spec_group):
    key = SpecKeyFactory(
        code="track_type",
        group=spec_group,
        unit="",
        value_type=SpecKey.ValueType.OPTION,
        is_filterable=True,
    )
    option = SpecOptionFactory(spec_key=key, code="gusenichnaya", name="Гусеничная")
    for index in range(2):
        item = MachineFactory(slug=f"tracked-{index}", brand=brand, machine_type=machine_type)
        MachineSpec.objects.create(machine=item, spec_key=key, value_option=option)

    options = build_facets()["options"]
    assert options[0]["values"][0] == {"code": "gusenichnaya", "name": "Гусеничная", "count": 2}


def test_boolean_facet_counts_only_true(brand, machine_type, spec_group):
    key = SpecKeyFactory(
        code="cabin_ac",
        group=spec_group,
        unit="",
        value_type=SpecKey.ValueType.BOOL,
        is_filterable=True,
    )
    yes = MachineFactory(slug="ac-yes", brand=brand, machine_type=machine_type)
    no = MachineFactory(slug="ac-no", brand=brand, machine_type=machine_type)
    MachineSpec.objects.create(machine=yes, spec_key=key, value_bool=True)
    MachineSpec.objects.create(machine=no, spec_key=key, value_bool=False)

    assert build_facets()["booleans"][0]["count"] == 1


def test_unpublished_machines_excluded_from_facets(machine_factory_set):
    machine_factory_set[0].is_published = False
    machine_factory_set[0].save()
    assert build_facets()["total"] == 2


def test_get_facets_uses_cache(machine_factory_set):
    """Повторный запрос берёт готовый результат, а не считает заново."""
    first = get_facets()
    assert cache.get(_cache_key(None)) is not None

    MachineFactory(
        slug="added-later",
        brand=machine_factory_set[0].brand,
        machine_type=machine_factory_set[0].machine_type,
    )
    # Сигнал сохранения уже поднял версию, поэтому пересчёт видит новую позицию.
    assert get_facets()["total"] == first["total"] + 1


def test_invalidation_is_version_based(machine_factory_set):
    """Ключей кэша столько же, сколько сочетаний фильтров.

    Перебрать их при сохранении машины невозможно, поэтому инвалидация идёт
    через версию каталога: старые ключи просто перестают использоваться.
    """
    get_facets()
    before = _cache_key(None)

    invalidate_facets()

    assert _cache_key(None) != before
    assert cache.get(_cache_key(None)) is None


def test_cache_key_differs_per_filter_set(machine_factory_set, brand, power_key):
    """Каждое сочетание условий кэшируется отдельно: счётчики у них разные."""
    empty = _cache_key(parse_filters(QueryDict("")))
    by_brand = _cache_key(parse_filters(QueryDict(f"brand={brand.slug}")))
    same_again = _cache_key(parse_filters(QueryDict(f"brand={brand.slug}")))

    assert empty != by_brand
    assert by_brand == same_again


def test_get_facets_force_refresh(machine_factory_set):
    get_facets()
    cache.set(
        _cache_key(None),
        {
            "total": 999,
            "brands": [],
            "machine_types": [],
            "numeric": [],
            "options": [],
            "booleans": [],
        },
    )
    assert get_facets()["total"] == 999
    assert get_facets(force_refresh=True)["total"] == 3


def test_saving_machine_invalidates_cache(machine_factory_set):
    get_facets()
    key_before = _cache_key(None)

    MachineFactory(
        slug="new-one",
        brand=machine_factory_set[0].brand,
        machine_type=machine_factory_set[0].machine_type,
    )

    # Сигнал сохранения поднимает версию сам — вручную ничего звать не нужно.
    assert _cache_key(None) != key_before


def test_saving_spec_invalidates_cache(machine_factory_set, power_key):
    get_facets()
    key_before = _cache_key(None)
    MachineSpec.objects.filter(spec_key=power_key).first().save()
    assert _cache_key(None) != key_before


def test_stock_change_invalidates_cache(machine_factory_set, branch):
    get_facets()
    key_before = _cache_key(None)
    machine_factory_set[0].stocks.first().save()
    assert _cache_key(None) != key_before


def test_annotate_selection_marks_current_choices(machine_factory_set, brand, power_key):
    filters = parse_filters(QueryDict(f"brand={brand.slug}&spec_engine_power_min=200"))
    annotated = annotate_selection(build_facets(), filters)

    assert annotated["brands"][0]["checked"] is True
    assert annotated["numeric"][0]["value_min"] == Decimal("200")
    assert annotated["numeric"][0]["value_max"] is None


def test_annotate_selection_marks_options(brand, machine_type, spec_group):
    key = SpecKeyFactory(
        code="track_type",
        group=spec_group,
        unit="",
        value_type=SpecKey.ValueType.OPTION,
        is_filterable=True,
    )
    option = SpecOptionFactory(spec_key=key, code="gusenichnaya", name="Гусеничная")
    item = MachineFactory(slug="tracked", brand=brand, machine_type=machine_type)
    MachineSpec.objects.create(machine=item, spec_key=key, value_option=option)

    filters = parse_filters(QueryDict("spec_track_type=gusenichnaya"), [key])
    annotated = annotate_selection(build_facets(), filters)
    assert annotated["options"][0]["values"][0]["checked"] is True


def test_annotate_selection_marks_booleans(brand, machine_type, spec_group):
    key = SpecKeyFactory(
        code="cabin_ac",
        group=spec_group,
        unit="",
        value_type=SpecKey.ValueType.BOOL,
        is_filterable=True,
    )
    item = MachineFactory(slug="ac", brand=brand, machine_type=machine_type)
    MachineSpec.objects.create(machine=item, spec_key=key, value_bool=True)

    filters = parse_filters(QueryDict("spec_cabin_ac=1"), [key])
    groups = annotate_selection(build_facets(), filters)["boolean_groups"]

    assert groups[0]["items"][0]["checked"] is True
    assert groups[0]["selected_count"] == 1


def test_boolean_filters_carry_their_group(brand, machine_type, spec_group):
    """У булевых параметров группа в справочнике есть, и панель её показывает.

    Без неё они выпадали из панели строками без заголовка, хотя каждый
    числовой и списочный параметр получал раздел со своим названием.
    """
    key = SpecKeyFactory(
        code="cabin_ac",
        name="Кондиционер в кабине",
        group=spec_group,
        unit="",
        value_type=SpecKey.ValueType.BOOL,
        is_filterable=True,
    )
    item = MachineFactory(slug="ac", brand=brand, machine_type=machine_type)
    MachineSpec.objects.create(machine=item, spec_key=key, value_bool=True)

    groups = annotate_selection(build_facets(), parse_filters(QueryDict(""), [key]))[
        "boolean_groups"
    ]

    assert groups[0]["name"] == spec_group.name
    assert [item["name"] for item in groups[0]["items"]] == ["Кондиционер в кабине"]
    assert groups[0]["selected_count"] == 0


def test_annotate_selection_counts_selected_brands(machine_factory_set, brand, power_key):
    """Число выбранных значений нужно заголовку свёрнутого раздела."""
    filters = parse_filters(QueryDict(f"brand={brand.slug}"))
    annotated = annotate_selection(build_facets(), filters)

    assert annotated["brands_selected"] == 1
    assert annotated["machine_types_selected"] == 0


def test_annotate_selection_marks_numeric_section_active(machine_factory_set, power_key):
    filters = parse_filters(QueryDict("spec_engine_power_max=300"))
    annotated = annotate_selection(build_facets(), filters)

    assert annotated["numeric"][0]["is_active"] is True


def test_annotate_selection_numeric_inactive_without_bounds(machine_factory_set, power_key):
    annotated = annotate_selection(build_facets(), parse_filters(QueryDict("")))
    assert annotated["numeric"][0]["is_active"] is False


def test_annotate_selection_counts_selected_options(brand, machine_type, spec_group):
    key = SpecKeyFactory(
        code="track_type",
        group=spec_group,
        unit="",
        value_type=SpecKey.ValueType.OPTION,
        is_filterable=True,
    )
    tracked = SpecOptionFactory(spec_key=key, code="gusenichnaya", name="Гусеничная")
    wheeled = SpecOptionFactory(spec_key=key, code="kolesnaya", name="Колёсная")
    for index, option in enumerate((tracked, wheeled)):
        item = MachineFactory(slug=f"opt-{index}", brand=brand, machine_type=machine_type)
        MachineSpec.objects.create(machine=item, spec_key=key, value_option=option)

    filters = parse_filters(
        QueryDict("spec_track_type=gusenichnaya&spec_track_type=kolesnaya"), [key]
    )
    annotated = annotate_selection(build_facets(), filters)

    assert annotated["options"][0]["selected_count"] == 2
