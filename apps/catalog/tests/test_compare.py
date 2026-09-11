"""Тесты сравнения моделей техники."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalog.factories import MachineFactory
from apps.specs.factories import SpecKeyFactory
from apps.specs.models import MachineSpec

pytestmark = pytest.mark.django_db


@pytest.fixture
def compared(brand, machine_type, power_key, spec_group):
    """Две машины: мощность различается, объём ковша одинаков."""
    bucket_key = SpecKeyFactory(
        code="bucket", name="Объём ковша", group=spec_group, unit="м³", decimals=2
    )
    machines = []
    for index, power in enumerate([150, 300], start=1):
        item = MachineFactory(
            slug=f"compare-{index}", name=f"PC{index}00", brand=brand, machine_type=machine_type
        )
        MachineSpec.objects.create(machine=item, spec_key=power_key, value_num=power)
        MachineSpec.objects.create(machine=item, spec_key=bucket_key, value_num=Decimal("2.5"))
        machines.append(item)
    return machines


def url(*machines) -> str:
    query = "&".join(f"m={item.slug}" for item in machines)
    return f"{reverse('catalog:machine-compare')}?{query}"


def test_compare_page_renders(client, compared):
    response = client.get(url(*compared))

    assert response.status_code == 200
    assert [item.slug for item in response.context["machines"]] == [
        compared[0].slug,
        compared[1].slug,
    ]


def test_differences_are_marked(client, compared):
    """Различия — то, ради чего сравнение и открывают."""
    groups = client.get(url(*compared)).context["spec_groups"]
    rows = {row["key"].code: row for group in groups for row in group["rows"]}

    assert rows["engine_power"]["is_different"] is True
    assert rows["bucket"]["is_different"] is False


def test_missing_value_shown_as_dash(client, compared, spec_group, brand, machine_type):
    """У третьей машины параметра нет — строка не должна исчезать."""
    third = MachineFactory(slug="compare-3", brand=brand, machine_type=machine_type)
    response = client.get(url(compared[0], third))

    rows = {row["key"].code: row for g in response.context["spec_groups"] for row in g["rows"]}
    assert rows["engine_power"]["values"][1] == "—"


def test_order_follows_request(client, compared):
    """Порядок в таблице — тот, в котором посетитель добавлял машины."""
    response = client.get(url(compared[1], compared[0]))
    assert [item.slug for item in response.context["machines"]] == [
        compared[1].slug,
        compared[0].slug,
    ]


def test_limit_is_enforced(client, brand, machine_type, power_key):
    machines = [
        MachineFactory(slug=f"many-{index}", brand=brand, machine_type=machine_type)
        for index in range(6)
    ]
    response = client.get(url(*machines))

    assert len(response.context["machines"]) == 4


def test_empty_state(client):
    response = client.get(reverse("catalog:machine-compare"))

    assert response.status_code == 200
    assert response.context["machines"] == []
    assert "Пока нечего сравнивать" in response.content.decode()


def test_unknown_slug_ignored(client, compared):
    response = client.get(f"{reverse('catalog:machine-compare')}?m=net-takoy&m={compared[0].slug}")
    assert len(response.context["machines"]) == 1


def test_unpublished_machine_excluded(client, compared):
    compared[0].is_published = False
    compared[0].save()

    assert len(client.get(url(*compared)).context["machines"]) == 1


def test_non_comparable_specs_hidden(client, compared, spec_group):
    """Параметр, снятый с сравнения, в таблицу не попадает."""
    hidden = SpecKeyFactory(code="hidden", name="Служебный", group=spec_group, is_comparable=False)
    MachineSpec.objects.create(machine=compared[0], spec_key=hidden, value_num=1)

    codes = {
        row["key"].code
        for g in client.get(url(*compared)).context["spec_groups"]
        for row in g["rows"]
    }
    assert "hidden" not in codes


def test_compare_page_is_not_indexed(client, compared):
    assert 'content="noindex,follow"' in client.get(url(*compared)).content.decode()
