"""Тесты раздела доставки."""

import pytest
from django.urls import reverse

from apps.company.models import DeliveryOption

pytestmark = pytest.mark.django_db


def make_option(**overrides) -> DeliveryOption:
    data = {
        "name": "Автовоз",
        "description": "Перевозка тралом или низкорамной платформой.",
        "lead_time": "3–7 дней",
        "note": "негабарит согласуется отдельно",
    }
    data.update(overrides)
    return DeliveryOption.objects.create(**data)


def test_delivery_page_lists_options(client, branch):
    make_option()
    make_option(name="Железная дорога", sort_order=20)

    content = client.get(reverse("company:delivery")).content.decode()

    assert "Автовоз" in content
    assert "Железная дорога" in content
    assert "3–7 дней" in content


def test_inactive_option_is_hidden(client, branch):
    make_option(name="Скрытый", is_active=False)

    assert "Скрытый" not in client.get(reverse("company:delivery")).content.decode()


def test_page_shows_the_warehouse_address(client, branch):
    make_option()

    content = client.get(reverse("company:delivery")).content.decode()

    assert branch.address in content


def test_empty_state(client, branch):
    content = client.get(reverse("company:delivery")).content.decode()

    assert "уточняйте у менеджера" in content


def test_options_shown_on_the_machine_card(client, machine):
    """Как привезут — вопрос первого разговора, отвечать надо на карточке."""
    make_option()
    make_option(name="Морем", sort_order=20)

    content = client.get(machine.get_absolute_url()).content.decode()

    assert "Доставка на объект" in content
    assert "Автовоз" in content
    assert "Морем" in content


def test_card_has_no_block_without_options(client, machine):
    assert "Доставка на объект" not in client.get(machine.get_absolute_url()).content.decode()


def test_card_links_to_the_delivery_page(client, machine):
    make_option()

    content = client.get(machine.get_absolute_url()).content.decode()

    assert reverse("company:delivery") in content


def test_ordering_follows_sort_order(client, branch):
    make_option(name="Второй", sort_order=20)
    make_option(name="Первый", sort_order=10)

    assert [option.name for option in DeliveryOption.objects.all()] == ["Первый", "Второй"]


def test_str_is_the_name():
    assert str(make_option()) == "Автовоз"
