"""Сигналы каталога: поисковый вектор, редиректы и сброс кэша фасетов."""

from django.contrib.postgres.search import SearchVector
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Machine, MachineStock
from .services.facets import invalidate_facets


def rebuild_search_vector(machine_id: int) -> None:
    """Пересчитывает поисковый вектор одной машины.

    Веса расставлены по важности совпадения: название модели (A) важнее бренда
    (B), бренд важнее описания (D).
    """
    Machine.objects.filter(pk=machine_id).update(
        search_vector=(
            SearchVector("name", weight="A", config="russian")
            + SearchVector("full_name", weight="A", config="russian")
            + SearchVector("series", weight="B", config="russian")
            + SearchVector("short_description", weight="C", config="russian")
            + SearchVector("description", weight="D", config="russian")
        )
    )


@receiver(pre_save, sender=Machine)
def remember_old_slug(sender, instance: Machine, **kwargs) -> None:
    """Запоминает прежний slug, чтобы после сохранения выписать редирект."""
    if not instance.pk:
        instance._old_slug = None
        return
    instance._old_slug = (
        Machine.objects.filter(pk=instance.pk).values_list("slug", flat=True).first()
    )


@receiver(post_save, sender=Machine)
def handle_machine_saved(sender, instance: Machine, created: bool, **kwargs) -> None:
    """Обновляет поисковый вектор, ведёт карту редиректов и сбрасывает фасеты.

    Редирект при смене слага важнее, чем кажется: у бренда тридцатилетняя история,
    и внешние ссылки на карточку переживают её переименование.
    """
    old_slug = getattr(instance, "_old_slug", None)
    if old_slug and old_slug != instance.slug:
        from apps.seo.models import RedirectRule

        RedirectRule.objects.update_or_create(
            old_path=f"/tehnika/{old_slug}/",
            defaults={
                "new_path": f"/tehnika/{instance.slug}/",
                "is_auto": True,
                "is_active": True,
                "note": "Создано автоматически при смене slug",
            },
        )

    # Пересчёт идёт в той же транзакции, что и само сохранение: поисковый
    # вектор обязан быть согласован с данными на любой момент времени, а
    # `update()` сигналов не вызывает, поэтому рекурсии здесь нет.
    rebuild_search_vector(instance.pk)
    invalidate_facets()


@receiver(post_delete, sender=Machine)
def handle_machine_deleted(sender, instance: Machine, **kwargs) -> None:
    invalidate_facets()


@receiver([post_save, post_delete], sender=MachineStock)
def handle_stock_changed(sender, instance: MachineStock, **kwargs) -> None:
    invalidate_facets()
