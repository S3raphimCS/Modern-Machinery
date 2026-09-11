"""Сигналы характеристик: пересчёт снимка для плитки каталога."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import MachineSpec


def rebuild_specs_cache(machine_id: int) -> None:
    """Пересобирает `Machine.specs_cache` — готовый к рендеру снимок.

    В плитке каталога выводятся две-три характеристики. Доставать их через
    JOIN на каждую карточку дорого, поэтому снимок хранится прямо на машине,
    а источником истины остаётся нормализованная таблица.
    """
    from apps.catalog.models import Machine

    specs = (
        MachineSpec.objects.filter(machine_id=machine_id, spec_key__is_in_card=True)
        .select_related("spec_key", "spec_key__group", "value_option")
        .order_by("spec_key__sort_order")
    )
    snapshot = {
        spec.spec_key.code: {
            "label": spec.spec_key.name,
            "value": spec.display_value,
            "unit": spec.spec_key.unit,
        }
        for spec in specs
    }
    Machine.objects.filter(pk=machine_id).update(specs_cache=snapshot)


@receiver([post_save, post_delete], sender=MachineSpec)
def handle_spec_changed(sender, instance: MachineSpec, **kwargs) -> None:
    from apps.catalog.services.facets import invalidate_facets

    rebuild_specs_cache(instance.machine_id)
    invalidate_facets()
