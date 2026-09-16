"""Тесты генератора демо-данных и учёта импортов."""

import pytest
from django.core.management import call_command

from apps.catalog.models import Brand, Machine, MachineStock
from apps.company.models import Branch, Department, Employee
from apps.content.models import NewsPost, ReviewSource, SiteSettings, Vacancy
from apps.imports.models import ImportRun, SourcePage
from apps.leads.models import ConsentVersion, LeadRoutingRule
from apps.parts.models import Part
from apps.services.models import Service
from apps.specs.models import MachineSpec, SpecKey

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    call_command("seed_demo", "--parts", 20, "--quiet", "--no-images")


def test_seed_creates_catalog(seeded):
    assert Machine.objects.count() > 50
    assert Brand.objects.count() == 7
    assert Part.objects.count() == 20
    assert Service.objects.count() == 15


def test_seed_creates_company_data(seeded):
    assert Branch.objects.get().city == "Хабаровск"
    assert Department.objects.count() == 5
    assert Employee.objects.count() == 6


def test_seed_creates_content(seeded):
    assert NewsPost.objects.count() > 0
    assert Vacancy.objects.count() > 0
    assert SiteSettings.objects.count() == 1
    assert ConsentVersion.objects.filter(code="lead-form").exists()


def test_seed_creates_routing_rules(seeded):
    """Без правил маршрутизации все заявки ушли бы на резервный адрес."""
    forklift_rule = LeadRoutingRule.objects.filter(
        machine_type__slug="vilochnyy-pogruzchik"
    ).first()
    assert forklift_rule is not None
    assert forklift_rule.emails == ["forklift@modernmachinery.example"]


def test_every_machine_has_specs(seeded):
    assert MachineSpec.objects.count() > Machine.objects.count()
    assert Machine.objects.filter(specs_cache={}).count() == 0


def test_every_machine_has_stock(seeded):
    assert MachineStock.objects.count() == Machine.objects.count()


def test_filterable_specs_exist(seeded):
    assert SpecKey.objects.filter(is_filterable=True).count() >= 8


def test_seed_is_idempotent(seeded):
    """Повторный прогон не создаёт дублей — это требование к любому импорту."""
    before = (Machine.objects.count(), Part.objects.count(), Service.objects.count())
    call_command("seed_demo", "--parts", 20, "--quiet", "--no-images")
    after = (Machine.objects.count(), Part.objects.count(), Service.objects.count())

    assert before == after


def test_seed_is_deterministic():
    """Одинаковое зерно даёт одинаковые данные: выдача каталога не должна плавать."""
    call_command("seed_demo", "--parts", 20, "--quiet", "--no-images", "--seed", 42)
    first = list(
        MachineSpec.objects.filter(spec_key__code="engine_power")
        .order_by("machine__slug")
        .values_list("machine__slug", "value_num")
    )

    MachineSpec.objects.all().delete()
    call_command("seed_demo", "--parts", 20, "--quiet", "--no-images", "--seed", 42)
    second = list(
        MachineSpec.objects.filter(spec_key__code="engine_power")
        .order_by("machine__slug")
        .values_list("machine__slug", "value_num")
    )

    assert first == second


def test_seed_records_import_run(seeded):
    run = ImportRun.objects.get()
    assert run.status == ImportRun.Status.SUCCESS
    assert run.stats["machines"] > 0
    assert run.finished_at is not None


def test_import_run_finish_sets_status():
    run = ImportRun.objects.create(source="legacy_site", kind="machines")
    run.finish(status=ImportRun.Status.FAILED, stats={"errors": 2}, log="Разбор не удался")
    run.refresh_from_db()

    assert run.status == ImportRun.Status.FAILED
    assert run.stats == {"errors": 2}
    assert run.log == "Разбор не удался"


def test_import_run_str():
    run = ImportRun.objects.create(source="demo", kind="seed_demo")
    assert "seed_demo" in str(run)


def test_source_page_str():
    page = SourcePage.objects.create(url="https://old.example/a", path="/a")
    assert str(page) == "/a"


def test_seed_creates_placeholder_image(brand, machine_type):
    """Генерация заглушки проверяется отдельно, а не полным прогоном seed.

    Рисование сотни картинок занимает больше времени, чем всё остальное
    наполнение, и держать его в каждом тесте наполнения незачем.
    """
    from apps.catalog.factories import MachineFactory
    from apps.imports.management.commands.seed_demo import Command

    machine = MachineFactory(brand=brand, machine_type=machine_type)
    Command()._create_machine_image(machine)

    image = machine.images.get()
    assert image.is_main is True
    assert image.thumbnail.name.endswith("-thumb.webp")
    assert image.image_webp


def test_seed_image_is_not_duplicated(brand, machine_type):
    from apps.catalog.factories import MachineFactory
    from apps.imports.management.commands.seed_demo import Command

    machine = MachineFactory(brand=brand, machine_type=machine_type)
    Command()._create_machine_image(machine)
    Command()._create_machine_image(machine)

    assert machine.images.count() == 1


def test_seeding_attaches_platform_logos():
    """Карточки площадок должны сразу показывать логотип, а не название."""
    call_command("seed_demo", verbosity=0)

    logos = {s.platform: s.logo.name for s in ReviewSource.objects.all()}

    assert logos, "площадки с отзывами должны создаваться"
    assert all(logos.values()), f"логотип подставлен не везде: {logos}"


def test_seeding_twice_keeps_one_logo():
    """Повторный запуск не должен копить копии логотипа в хранилище.

    Хранилище приписывает к занятому имени случайный суффикс, поэтому
    безусловное сохранение оставляло бы при каждом запуске новый файл.
    """
    call_command("seed_demo", verbosity=0)
    first = {s.platform: s.logo.name for s in ReviewSource.objects.all()}

    call_command("seed_demo", verbosity=0)
    second = {s.platform: s.logo.name for s in ReviewSource.objects.all()}

    assert first == second
