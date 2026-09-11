"""Тесты справочника характеристик и ограничений на значения."""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.catalog.models import Machine
from apps.specs.factories import SpecKeyFactory, SpecOptionFactory
from apps.specs.models import MachineSpec, SpecKey

pytestmark = pytest.mark.django_db


def test_spec_key_str_includes_unit(power_key):
    assert str(power_key) == "Мощность двигателя, кВт"


def test_spec_key_str_without_unit(spec_group):
    key = SpecKeyFactory(name="Тип привода", unit="", group=spec_group)
    assert str(key) == "Тип привода"


def test_format_value_respects_decimals(machine, spec_group):
    key = SpecKeyFactory(name="Объём ковша", unit="м³", group=spec_group, decimals=2)
    spec = MachineSpec.objects.create(machine=machine, spec_key=key, value_num=Decimal("0.9"))
    assert spec.display_value == "0.90"


def test_format_value_renders_range(machine, spec_group):
    key = SpecKeyFactory(name="Глубина копания", unit="м", group=spec_group, decimals=1)
    spec = MachineSpec.objects.create(
        machine=machine,
        spec_key=key,
        value_num=Decimal("6.6"),
        value_num_max=Decimal("7.4"),
    )
    assert spec.display_value == "6.6–7.4"


@pytest.mark.parametrize(("value", "expected"), [(True, "Есть"), (False, "Нет")])
def test_format_value_boolean(machine, spec_group, value, expected):
    key = SpecKeyFactory(
        name="Кондиционер", unit="", group=spec_group, value_type=SpecKey.ValueType.BOOL
    )
    spec = MachineSpec.objects.create(machine=machine, spec_key=key, value_bool=value)
    assert spec.display_value == expected


def test_format_value_option(machine, spec_group):
    key = SpecKeyFactory(
        name="Ходовая", unit="", group=spec_group, value_type=SpecKey.ValueType.OPTION
    )
    option = SpecOptionFactory(spec_key=key, name="Гусеничная")
    spec = MachineSpec.objects.create(machine=machine, spec_key=key, value_option=option)
    assert spec.display_value == "Гусеничная"


def test_format_value_string(machine, spec_group):
    key = SpecKeyFactory(
        name="Двигатель", unit="", group=spec_group, value_type=SpecKey.ValueType.STRING
    )
    spec = MachineSpec.objects.create(machine=machine, spec_key=key, value_str="SAA6D125E-5")
    assert spec.display_value == "SAA6D125E-5"


def test_machine_spec_rejects_two_values(machine, power_key):
    """Ограничение БД: ровно одно значение из четырёх.

    Без него непонятно, что показывать в карточке и по чему фильтровать.
    """
    with pytest.raises(IntegrityError), transaction.atomic():
        MachineSpec.objects.create(
            machine=machine,
            spec_key=power_key,
            value_num=Decimal("100"),
            value_str="сто",
        )


def test_machine_spec_rejects_empty_value(machine, power_key):
    with pytest.raises(IntegrityError), transaction.atomic():
        MachineSpec.objects.create(machine=machine, spec_key=power_key)


def test_machine_spec_rejects_inverted_range(machine, power_key):
    """Верхняя граница диапазона не может быть меньше нижней."""
    with pytest.raises(IntegrityError), transaction.atomic():
        MachineSpec.objects.create(
            machine=machine,
            spec_key=power_key,
            value_num=Decimal("300"),
            value_num_max=Decimal("100"),
        )


def test_machine_spec_rejects_max_without_min(machine, power_key):
    with pytest.raises(IntegrityError), transaction.atomic():
        MachineSpec.objects.create(
            machine=machine, spec_key=power_key, value_num_max=Decimal("100")
        )


def test_machine_spec_unique_per_key(machine, power_key):
    MachineSpec.objects.create(machine=machine, spec_key=power_key, value_num=Decimal("100"))
    with pytest.raises(IntegrityError), transaction.atomic():
        MachineSpec.objects.create(machine=machine, spec_key=power_key, value_num=Decimal("200"))


def test_spec_option_unique_code_per_key(spec_group):
    key = SpecKeyFactory(group=spec_group, value_type=SpecKey.ValueType.OPTION)
    SpecOptionFactory(spec_key=key, code="gusenichnaya")
    with pytest.raises(IntegrityError), transaction.atomic():
        SpecOptionFactory(spec_key=key, code="gusenichnaya")


def test_saving_spec_rebuilds_machine_cache(machine, power_key):
    """Снимок характеристик пересобирается сигналом.

    Плитка каталога читает `specs_cache`, а не делает JOIN на каждую карточку.
    """
    MachineSpec.objects.create(machine=machine, spec_key=power_key, value_num=Decimal("257"))
    machine.refresh_from_db()

    assert machine.specs_cache["engine_power"] == {
        "label": "Мощность двигателя",
        "value": "257",
        "unit": "кВт",
    }


def test_deleting_spec_updates_machine_cache(machine, power_key):
    spec = MachineSpec.objects.create(machine=machine, spec_key=power_key, value_num=Decimal("257"))
    spec.delete()
    machine.refresh_from_db()
    assert machine.specs_cache == {}


def test_cache_skips_keys_not_shown_in_card(machine, spec_group):
    """В снимок попадают только параметры, помеченные для вывода в плитке."""
    hidden = SpecKeyFactory(group=spec_group, is_in_card=False, name="Скрытый")
    MachineSpec.objects.create(machine=machine, spec_key=hidden, value_num=Decimal("1"))
    machine.refresh_from_db()
    assert machine.specs_cache == {}


def test_str_of_machine_spec(machine, power_key):
    spec = MachineSpec.objects.create(machine=machine, spec_key=power_key, value_num=Decimal("257"))
    assert "Мощность двигателя" in str(spec)


def test_spec_group_str(spec_group):
    assert str(spec_group) == "Двигатель"


def test_spec_option_str(spec_group):
    key = SpecKeyFactory(group=spec_group, value_type=SpecKey.ValueType.OPTION)
    assert str(SpecOptionFactory(spec_key=key, name="Колёсная")) == "Колёсная"


def test_machine_not_deleted_when_spec_key_protected(machine, power_key):
    """Справочный параметр под PROTECT: удаление не должно унести значения."""
    MachineSpec.objects.create(machine=machine, spec_key=power_key, value_num=Decimal("1"))
    with pytest.raises(ProtectedError), transaction.atomic():
        power_key.delete()
    assert Machine.objects.filter(pk=machine.pk).exists()
