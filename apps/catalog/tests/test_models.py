"""Тесты моделей каталога техники."""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.catalog.factories import (
    BrandFactory,
    MachineFactory,
    MachineImageFactory,
    MachineStockFactory,
)
from apps.catalog.models import Brand, Machine, MachineStock

pytestmark = pytest.mark.django_db


def test_machine_str_uses_full_name(machine):
    machine.full_name = "Экскаватор Komatsu PC400-8"
    assert str(machine) == "Экскаватор Komatsu PC400-8"


def test_machine_str_falls_back_to_brand_and_name(brand, machine_type):
    item = MachineFactory(name="PC400-8", full_name="", brand=brand, machine_type=machine_type)
    assert str(item) == "Komatsu PC400-8"


def test_machine_absolute_url(machine):
    assert machine.get_absolute_url() == "/tehnika/komatsu-pc400-8/"


def test_price_hidden_by_default(machine):
    """В B2B цена договорная, поэтому по умолчанию она скрыта."""
    assert machine.is_price_on_request is True
    assert machine.display_price == "Цена по запросу"


def test_price_shown_when_enabled(machine):
    machine.price = Decimal("18500000")
    machine.is_price_on_request = False
    machine.save()
    assert machine.display_price == "18 500 000 ₽"


def test_price_on_request_wins_over_filled_price(machine):
    machine.price = Decimal("100")
    machine.is_price_on_request = True
    machine.save()
    assert machine.display_price == "Цена по запросу"


def test_only_one_main_image_allowed(machine):
    """Частичный уникальный индекс: две «главных» картинки ломают вёрстку."""
    MachineImageFactory(machine=machine, is_main=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        MachineImageFactory(machine=machine, is_main=True)


def test_several_secondary_images_allowed(machine):
    MachineImageFactory(machine=machine, is_main=False)
    MachineImageFactory(machine=machine, is_main=False)
    assert machine.images.count() == 2


def test_main_image_prefers_flagged_one(machine):
    MachineImageFactory(machine=machine, is_main=False, sort_order=1)
    main = MachineImageFactory(machine=machine, is_main=True, sort_order=50)
    assert machine.main_image == main


def test_main_image_falls_back_to_first(machine):
    first = MachineImageFactory(machine=machine, is_main=False, sort_order=1)
    MachineImageFactory(machine=machine, is_main=False, sort_order=2)
    assert machine.main_image == first


def test_main_image_none_when_no_images(machine):
    assert machine.main_image is None


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([MachineStock.Status.ON_ORDER, MachineStock.Status.IN_STOCK], "in_stock"),
        ([MachineStock.Status.ON_ORDER, MachineStock.Status.LOW], "low"),
        ([MachineStock.Status.ON_ORDER], "on_order"),
        ([MachineStock.Status.NONE], "none"),
        ([], "none"),
    ],
)
def test_stock_status_picks_best_available(machine, branch, statuses, expected):
    """Сводный статус берёт лучший из складов: «в наличии» важнее «под заказ»."""
    from apps.company.factories import BranchFactory

    for index, status in enumerate(statuses):
        target = branch if index == 0 else BranchFactory(slug=f"branch-{index}", city=f"Г{index}")
        MachineStockFactory(machine=machine, branch=target, status=status)
    assert machine.stock_status == expected


def test_stock_unique_per_branch(machine, branch):
    MachineStockFactory(machine=machine, branch=branch)
    with pytest.raises(IntegrityError), transaction.atomic():
        MachineStockFactory(machine=machine, branch=branch)


def test_brand_protected_from_deletion(machine):
    """Удаление бренда не должно каскадом снести карточки техники."""
    with pytest.raises(ProtectedError), transaction.atomic():
        machine.brand.delete()
    assert Machine.objects.filter(pk=machine.pk).exists()


def test_brand_visible_queryset():
    BrandFactory(slug="active-brand", is_active=True)
    BrandFactory(slug="hidden-brand", is_active=False)
    assert Brand.objects.visible().count() == 1


def test_category_absolute_url(category):
    assert category.get_absolute_url() == f"/?category={category.slug}"


def test_machine_type_str(machine_type):
    assert str(machine_type) == "Экскаватор"


def test_stock_str(machine, branch):
    stock = MachineStockFactory(machine=machine, branch=branch)
    assert "В наличии" in str(stock)


def test_document_str(machine):
    from apps.catalog.factories import MachineDocumentFactory

    assert str(MachineDocumentFactory(machine=machine, title="Спецификация")) == "Спецификация"


def test_image_str_uses_alt(machine):
    assert (
        str(MachineImageFactory(machine=machine, alt="Экскаватор в работе"))
        == "Экскаватор в работе"
    )
