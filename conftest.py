"""Общие фикстуры для всех тестов."""

import pytest
from django.core.cache import cache

from apps.catalog.factories import (
    BrandFactory,
    CategoryFactory,
    MachineFactory,
    MachineStockFactory,
    MachineTypeFactory,
)
from apps.company.factories import BranchFactory, DepartmentFactory
from apps.leads.factories import ConsentVersionFactory
from apps.specs.factories import SpecGroupFactory, SpecKeyFactory
from apps.specs.models import MachineSpec, SpecKey
from apps.users.factories import StaffUserFactory, UserFactory


@pytest.fixture(autouse=True)
def _clear_cache():
    """Кэш фасетов и меню общий для процесса, поэтому чистится между тестами.

    Без этого тест, изменивший каталог, влиял бы на соседний через кэш.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def branch(db):
    return BranchFactory()


@pytest.fixture
def department(db):
    return DepartmentFactory(code="sales", name="Отдел продаж техники")


@pytest.fixture
def consent(db):
    return ConsentVersionFactory()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def staff_user(db):
    return StaffUserFactory(username="admin", email="admin@modernmachinery.ru")


@pytest.fixture
def admin_client(client, staff_user):
    client.force_login(staff_user)
    return client


@pytest.fixture
def brand(db):
    return BrandFactory(slug="komatsu", name="Komatsu")


@pytest.fixture
def machine_type(db):
    return MachineTypeFactory(slug="ekskavator", name="Экскаватор")


@pytest.fixture
def category(db):
    return CategoryFactory(slug="ekskavatory", name="Экскаваторы")


@pytest.fixture
def spec_group(db):
    return SpecGroupFactory(code="dvigatel", name="Двигатель")


@pytest.fixture
def power_key(spec_group):
    """Числовой фильтруемый параметр — основа большинства тестов фильтрации."""
    return SpecKeyFactory(
        code="engine_power",
        name="Мощность двигателя",
        group=spec_group,
        unit="кВт",
        value_type=SpecKey.ValueType.NUMBER,
        is_filterable=True,
        is_in_card=True,
        aliases=["Мощность двиг.", "Мощность"],
    )


@pytest.fixture
def machine(brand, machine_type):
    return MachineFactory(
        slug="komatsu-pc400-8", name="PC400-8", brand=brand, machine_type=machine_type
    )


@pytest.fixture
def machine_factory_set(brand, machine_type, power_key, branch):
    """Три машины с разной мощностью: 150, 250 и 350 кВт.

    Набор подобран так, чтобы одна граница фильтра всегда отсекала ровно одну
    позицию — по числу результатов сразу видно, что именно сломалось.
    """
    machines = []
    for index, power in enumerate([150, 250, 350], start=1):
        item = MachineFactory(
            slug=f"machine-power-{index}",
            name=f"PC{index}00",
            brand=brand,
            machine_type=machine_type,
        )
        MachineSpec.objects.create(machine=item, spec_key=power_key, value_num=power)
        MachineStockFactory(machine=item, branch=branch)
        machines.append(item)
    return machines
