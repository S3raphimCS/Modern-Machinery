"""Тесты сигналов каталога: поисковый вектор и автоматические редиректы."""

import pytest

from apps.catalog.models import Machine
from apps.seo.models import RedirectRule

pytestmark = pytest.mark.django_db


def test_search_vector_filled_on_save(machine):
    machine.refresh_from_db()
    assert machine.search_vector is not None


def test_search_finds_by_name(machine):
    assert Machine.objects.visible().search("PC400").count() == 1


def test_search_finds_by_description(brand, machine_type):
    from apps.catalog.factories import MachineFactory

    MachineFactory(
        slug="with-text",
        name="XX1",
        brand=brand,
        machine_type=machine_type,
        description="Гидравлический экскаватор для карьерных работ",
    )
    assert Machine.objects.visible().search("карьерных").count() == 1


def test_slug_change_creates_redirect(machine):
    """Ссылочная масса переживает переименование карточки.

    У бренда тридцатилетняя история, и внешние ссылки на карточку живут дольше,
    чем её текущий адрес.
    """
    old_url = machine.get_absolute_url()
    machine.slug = "komatsu-pc400-8-new"
    machine.save()

    rule = RedirectRule.objects.get(old_path=old_url)
    assert rule.new_path == "/tehnika/komatsu-pc400-8-new/"
    assert rule.status_code == 301
    assert rule.is_auto is True


def test_no_redirect_when_slug_unchanged(machine):
    machine.name = "Новое название"
    machine.save()
    assert RedirectRule.objects.count() == 0


def test_no_redirect_on_creation(brand, machine_type):
    from apps.catalog.factories import MachineFactory

    MachineFactory(slug="fresh-one", brand=brand, machine_type=machine_type)
    assert RedirectRule.objects.count() == 0


def test_repeated_slug_change_updates_rule(machine):
    machine.slug = "second-slug"
    machine.save()
    machine.slug = "third-slug"
    machine.save()

    assert RedirectRule.objects.count() == 2
    assert RedirectRule.objects.get(old_path="/tehnika/second-slug/").new_path == (
        "/tehnika/third-slug/"
    )
