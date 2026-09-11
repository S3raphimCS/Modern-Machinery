"""Тесты фасетной фильтрации каталога.

Фильтры — главное отличие нового каталога от старого сайта, поэтому проверяются
и разбор параметров, и итоговая выборка, и поведение на мусорном вводе.
"""

from decimal import Decimal

import pytest
from django.http import QueryDict

from apps.catalog.factories import MachineFactory, MachineStockFactory
from apps.catalog.models import Machine, MachineStock
from apps.catalog.services.filters import SORT_OPTIONS, apply_filters, parse_filters
from apps.specs.factories import SpecKeyFactory, SpecOptionFactory
from apps.specs.models import MachineSpec, SpecKey

pytestmark = pytest.mark.django_db


def visible():
    return Machine.objects.visible()


def qd(query: str) -> QueryDict:
    return QueryDict(query)


def test_parse_filters_reads_plain_parameters(power_key):
    filters = parse_filters(qd("q=PC400&brand=komatsu&type=ekskavator&in_stock=1&sort=name"))

    assert filters.query == "PC400"
    assert filters.brands == ["komatsu"]
    assert filters.machine_types == ["ekskavator"]
    assert filters.in_stock_only is True
    assert filters.sort == "name"
    assert filters.is_empty is False


def test_parse_filters_empty_is_detected(power_key):
    assert parse_filters(qd("")).is_empty is True


def test_parse_filters_reads_numeric_bounds(power_key):
    filters = parse_filters(qd("spec_engine_power_min=150&spec_engine_power_max=300"))
    assert filters.numeric["engine_power"] == (Decimal("150"), Decimal("300"))


def test_parse_filters_accepts_comma_decimal(power_key):
    filters = parse_filters(qd("spec_engine_power_min=1,5"))
    assert filters.numeric["engine_power"] == (Decimal("1.5"), None)


def test_parse_filters_ignores_broken_numbers(power_key):
    """Посетитель мог поправить ссылку руками — это не повод отдавать 500."""
    filters = parse_filters(qd("spec_engine_power_min=много"))
    assert filters.numeric == {}


def test_parse_filters_ignores_unknown_spec(power_key):
    assert parse_filters(qd("spec_unknown_min=10")).numeric == {}


def test_parse_filters_ignores_unknown_sort(power_key):
    assert parse_filters(qd("sort=; DROP TABLE")).sort == "default"


def test_parse_filters_reads_boolean_spec(spec_group):
    key = SpecKeyFactory(
        code="cabin_ac", group=spec_group, value_type=SpecKey.ValueType.BOOL, is_filterable=True
    )
    filters = parse_filters(qd("spec_cabin_ac=1"), [key])
    assert filters.booleans == {"cabin_ac": True}


def test_parse_filters_reads_option_spec(spec_group):
    key = SpecKeyFactory(
        code="track_type", group=spec_group, value_type=SpecKey.ValueType.OPTION, is_filterable=True
    )
    filters = parse_filters(qd("spec_track_type=gusenichnaya"), [key])
    assert filters.options == {"track_type": ["gusenichnaya"]}


def test_filter_by_minimum(machine_factory_set, power_key):
    filters = parse_filters(qd("spec_engine_power_min=200"))
    assert apply_filters(visible(), filters).count() == 2


def test_filter_by_maximum(machine_factory_set, power_key):
    filters = parse_filters(qd("spec_engine_power_max=200"))
    assert apply_filters(visible(), filters).count() == 1


def test_filter_by_range(machine_factory_set, power_key):
    filters = parse_filters(qd("spec_engine_power_min=200&spec_engine_power_max=300"))
    assert apply_filters(visible(), filters).count() == 1


def test_filter_matches_range_valued_spec(brand, machine_type, spec_group):
    """Диапазонная характеристика должна попадать под фильтр «от».

    Машина с глубиной копания 6,6–7,4 м обязана находиться по запросу «от 7»:
    именно ради этого у значения есть верхняя граница.
    """
    key = SpecKeyFactory(code="digging_depth", group=spec_group, unit="м", decimals=1)
    machine = MachineFactory(brand=brand, machine_type=machine_type)
    MachineSpec.objects.create(
        machine=machine,
        spec_key=key,
        value_num=Decimal("6.6"),
        value_num_max=Decimal("7.4"),
    )

    assert apply_filters(visible(), parse_filters(qd("spec_digging_depth_min=7"))).count() == 1
    assert apply_filters(visible(), parse_filters(qd("spec_digging_depth_min=8"))).count() == 0


def test_filter_by_brand_and_type(machine_factory_set, brand, machine_type):
    assert apply_filters(visible(), parse_filters(qd(f"brand={brand.slug}"))).count() == 3
    assert apply_filters(visible(), parse_filters(qd("brand=nonexistent"))).count() == 0
    assert apply_filters(visible(), parse_filters(qd(f"type={machine_type.slug}"))).count() == 3


def test_filter_by_category(machine_factory_set, category):
    machine_factory_set[0].categories.add(category)
    filters = parse_filters(qd(f"category={category.slug}"))
    assert apply_filters(visible(), filters).count() == 1


def test_filter_by_stock(machine_factory_set, branch, brand, machine_type):
    """«Только в наличии» отсекает позиции под заказ."""
    on_order = MachineFactory(slug="on-order", brand=brand, machine_type=machine_type)
    MachineStockFactory(machine=on_order, branch=branch, status=MachineStock.Status.ON_ORDER)

    assert apply_filters(visible(), parse_filters(qd("in_stock=1"))).count() == 3
    assert visible().count() == 4


def test_filter_by_boolean_spec(brand, machine_type, spec_group):
    key = SpecKeyFactory(
        code="cabin_ac",
        group=spec_group,
        value_type=SpecKey.ValueType.BOOL,
        is_filterable=True,
        unit="",
    )
    with_ac = MachineFactory(slug="with-ac", brand=brand, machine_type=machine_type)
    without_ac = MachineFactory(slug="without-ac", brand=brand, machine_type=machine_type)
    MachineSpec.objects.create(machine=with_ac, spec_key=key, value_bool=True)
    MachineSpec.objects.create(machine=without_ac, spec_key=key, value_bool=False)

    filters = parse_filters(qd("spec_cabin_ac=1"), [key])
    assert list(apply_filters(visible(), filters)) == [with_ac]


def test_filter_by_option_spec(brand, machine_type, spec_group):
    key = SpecKeyFactory(
        code="track_type",
        group=spec_group,
        value_type=SpecKey.ValueType.OPTION,
        is_filterable=True,
        unit="",
    )
    tracked = SpecOptionFactory(spec_key=key, code="gusenichnaya", name="Гусеничная")
    wheeled = SpecOptionFactory(spec_key=key, code="kolesnaya", name="Колёсная")
    first = MachineFactory(slug="tracked", brand=brand, machine_type=machine_type)
    second = MachineFactory(slug="wheeled", brand=brand, machine_type=machine_type)
    MachineSpec.objects.create(machine=first, spec_key=key, value_option=tracked)
    MachineSpec.objects.create(machine=second, spec_key=key, value_option=wheeled)

    filters = parse_filters(qd("spec_track_type=gusenichnaya"), [key])
    assert list(apply_filters(visible(), filters)) == [first]


def test_filters_combine_with_and_semantics(machine_factory_set, power_key, brand):
    """Несколько условий сужают выдачу, а не расширяют её."""
    filters = parse_filters(qd(f"brand={brand.slug}&spec_engine_power_min=300"))
    assert apply_filters(visible(), filters).count() == 1


def test_filters_do_not_duplicate_rows(machine_factory_set, power_key, category):
    """Несколько EXISTS-подзапросов не должны размножать строки.

    Ровно поэтому фильтрация сделана через EXISTS, а не цепочкой JOIN.
    """
    for machine in machine_factory_set:
        machine.categories.add(category)
    filters = parse_filters(
        qd(f"category={category.slug}&spec_engine_power_min=100&spec_engine_power_max=400")
    )
    result = apply_filters(visible(), filters)
    assert result.count() == len({item.pk for item in result})


def test_search_filters_and_ranks(machine_factory_set, brand, machine_type):
    target = MachineFactory(
        slug="pc400-search",
        name="PC400-8",
        full_name="Экскаватор PC400-8",
        brand=brand,
        machine_type=machine_type,
    )
    from apps.catalog.signals import rebuild_search_vector

    for item in [*machine_factory_set, target]:
        rebuild_search_vector(item.pk)

    filters = parse_filters(qd("q=PC400"))
    assert list(apply_filters(visible(), filters)) == [target]


def test_blank_search_returns_everything(machine_factory_set):
    filters = parse_filters(qd("q=   "))
    assert apply_filters(visible(), filters).count() == 3


@pytest.mark.parametrize("sort", list(SORT_OPTIONS))
def test_sorting_options_are_valid(machine_factory_set, sort):
    """Каждый вариант сортировки должен собираться в корректный запрос."""
    filters = parse_filters(qd(f"sort={sort}"))
    assert apply_filters(visible(), filters).count() == 3


def test_unpublished_machines_never_visible(machine_factory_set):
    machine_factory_set[0].is_published = False
    machine_factory_set[0].save()
    assert visible().count() == 2


def test_active_count_is_zero_without_filters(power_key):
    assert parse_filters(qd("")).active_count == 0


def test_active_count_sums_conditions(power_key):
    """Панель фильтров свёрнута, поэтому число условий выводится на кнопке."""
    filters = parse_filters(qd("brand=komatsu&brand=bomag&type=ekskavator&in_stock=1"))
    assert filters.active_count == 4


def test_active_count_treats_range_as_one_condition(power_key):
    """«От и до» по одному параметру — одно условие, как его видит человек."""
    filters = parse_filters(qd("spec_engine_power_min=150&spec_engine_power_max=300"))
    assert filters.active_count == 1


def test_active_count_ignores_search_and_sorting(power_key):
    """Поиск и сортировка — не фильтры: они не сужают набор условий панели."""
    assert parse_filters(qd("q=PC400&sort=name")).active_count == 0


def test_active_count_counts_options_and_booleans(spec_group):
    option_key = SpecKeyFactory(
        code="track_type",
        group=spec_group,
        unit="",
        value_type=SpecKey.ValueType.OPTION,
        is_filterable=True,
    )
    bool_key = SpecKeyFactory(
        code="cabin_ac",
        group=spec_group,
        unit="",
        value_type=SpecKey.ValueType.BOOL,
        is_filterable=True,
    )

    filters = parse_filters(
        qd("spec_track_type=gusenichnaya&spec_track_type=kolesnaya&spec_cabin_ac=1"),
        [option_key, bool_key],
    )
    assert filters.active_count == 3
