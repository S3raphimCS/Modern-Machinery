"""Фасеты каталога — счётчики и диапазоны для панели фильтров.

Счётчики считаются с учётом уже выбранных условий, но каждое измерение
исключает само себя. Это стандартное поведение фасетного поиска, и оно важнее,
чем кажется: если считать по всему каталогу, панель обещает «Komatsu — 43»
при выбранном типе «Каток», человек кликает и получает пустую выдачу. А если
считать по полностью отфильтрованной выборке, у всех остальных брендов встанут
нули и сменить бренд станет невозможно.

Результат кэшируется. Ключ включает и состав фильтров, и версию каталога:
при изменении данных версия увеличивается, и все накопленные варианты
перестают использоваться разом.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Max, Min

from apps.specs.models import SpecKey

FACETS_CACHE_KEY = "catalog:facets:v2"
FACETS_VERSION_KEY = "catalog:facets:version"


def _version() -> int:
    """Текущая версия каталога.

    Инвалидация сделана через версию, а не удалением ключей: вариантов кэша
    столько же, сколько сочетаний фильтров, и перебрать их при сохранении
    машины невозможно.
    """
    version = cache.get(FACETS_VERSION_KEY)
    if version is None:
        version = 1
        cache.set(FACETS_VERSION_KEY, version, None)
    return version


def _cache_key(filters) -> str:
    if filters is None or filters.is_empty:
        signature = "all"
    else:
        payload = json.dumps(
            {
                "q": filters.query,
                "brands": sorted(filters.brands),
                "types": sorted(filters.machine_types),
                "categories": sorted(filters.categories),
                "stock": filters.in_stock_only,
                "numeric": {k: [str(v[0]), str(v[1])] for k, v in sorted(filters.numeric.items())},
                "options": {k: sorted(v) for k, v in sorted(filters.options.items())},
                "booleans": dict(sorted(filters.booleans.items())),
            },
            sort_keys=True,
        )
        signature = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{FACETS_CACHE_KEY}:{_version()}:{signature}"


def _without(filters, *, dimension: str | None = None, spec_code: str | None = None):
    """Копия фильтров без одного измерения.

    Нужна, чтобы счётчики раздела не обнулялись собственным выбором.
    """
    if filters is None:
        return None
    if dimension == "brands":
        return replace(filters, brands=[])
    if dimension == "machine_types":
        return replace(filters, machine_types=[])
    if spec_code is not None:
        return replace(
            filters,
            numeric={k: v for k, v in filters.numeric.items() if k != spec_code},
            options={k: v for k, v in filters.options.items() if k != spec_code},
            booleans={k: v for k, v in filters.booleans.items() if k != spec_code},
        )
    return filters


def _queryset(filters, **exclude):
    """Выборка машин с применёнными фильтрами, кроме исключённого измерения."""
    from apps.catalog.models import Machine
    from apps.catalog.services.filters import apply_filters

    queryset = Machine.objects.visible()
    reduced = _without(filters, **exclude)
    if reduced is None:
        return queryset
    return apply_filters(queryset, reduced)


def _decimal_to_float(value):
    return float(value) if isinstance(value, Decimal) else value


def _counts_by(queryset, field: str) -> dict:
    """Считает число машин по значению поля.

    `order_by()` сбрасывает сортировку: без этого Django добавит поля сортировки
    в GROUP BY и разобьёт группы на части.
    """
    rows = queryset.order_by().values(field).annotate(count=Count("pk", distinct=True))
    return {row[field]: row["count"] for row in rows}


def build_facets(filters=None) -> dict:
    """Считает фасеты с учётом текущего выбора."""
    from apps.catalog.models import Brand, Machine, MachineType

    brand_counts = _counts_by(_queryset(filters, dimension="brands"), "brand__slug")
    brands = [
        {"slug": item.slug, "name": item.name, "count": brand_counts.get(item.slug, 0)}
        for item in Brand.objects.visible().order_by("sort_order", "name")
        if item.slug in brand_counts or Machine.objects.visible().filter(brand=item).exists()
    ]

    type_counts = _counts_by(_queryset(filters, dimension="machine_types"), "machine_type__slug")
    machine_types = [
        {"slug": item.slug, "name": item.name, "count": type_counts.get(item.slug, 0)}
        for item in MachineType.objects.order_by("sort_order", "name")
        if item.slug in type_counts or Machine.objects.visible().filter(machine_type=item).exists()
    ]

    numeric: list[dict] = []
    options: list[dict] = []
    booleans: list[dict] = []

    spec_keys = (
        SpecKey.objects.filter(is_filterable=True)
        .select_related("group")
        .prefetch_related("options")
        .order_by("group__sort_order", "sort_order", "name")
    )

    for key in spec_keys:
        base = {
            "code": key.code,
            "name": key.name,
            "unit": key.unit,
            "group": key.group.name,
            "decimals": key.decimals,
        }
        # Каждый параметр считается по выборке без него самого: иначе выбранный
        # диапазон сам себя обрежет и шкалу нельзя будет расширить обратно.
        scope = _queryset(filters, spec_code=key.code).values("pk")

        if key.value_type == SpecKey.ValueType.NUMBER:
            bounds = key.values.filter(machine__in=scope).aggregate(
                min_value=Min("value_num"),
                max_value=Max("value_num_max"),
                max_single=Max("value_num"),
            )
            low = bounds["min_value"]
            high = max(
                (v for v in (bounds["max_value"], bounds["max_single"]) if v is not None),
                default=None,
            )
            if low is None or high is None:
                continue
            numeric.append({**base, "min": _decimal_to_float(low), "max": _decimal_to_float(high)})
        elif key.value_type == SpecKey.ValueType.OPTION:
            rows = list(
                key.values.filter(machine__in=scope, value_option__isnull=False)
                .values("value_option__code", "value_option__name")
                .annotate(count=Count("id"))
                .order_by("-count")
            )
            if not rows:
                continue
            options.append(
                {
                    **base,
                    "values": [
                        {
                            "code": row["value_option__code"],
                            "name": row["value_option__name"],
                            "count": row["count"],
                        }
                        for row in rows
                    ],
                }
            )
        elif key.value_type == SpecKey.ValueType.BOOL:
            count = key.values.filter(machine__in=scope, value_bool=True).count()
            if not count:
                continue
            booleans.append({**base, "count": count})

    return {
        "brands": brands,
        "machine_types": machine_types,
        "numeric": numeric,
        "options": options,
        "booleans": booleans,
        # Итог по всем условиям сразу — это число и видит посетитель в выдаче.
        "total": _queryset(filters).count(),
    }


def get_facets(filters=None, *, force_refresh: bool = False) -> dict:
    """Отдаёт фасеты из кэша, пересчитывая их при необходимости."""
    key = _cache_key(filters)
    if not force_refresh:
        cached = cache.get(key)
        if cached is not None:
            return cached
    facets = build_facets(filters)
    cache.set(key, facets, settings.CATALOG_FACETS_CACHE_SECONDS)
    return facets


def invalidate_facets() -> None:
    """Обесценивает все накопленные варианты кэша. Вызывается сигналами."""
    try:
        cache.incr(FACETS_VERSION_KEY)
    except ValueError:
        # Ключа ещё нет — считать нечего, достаточно завести его.
        cache.set(FACETS_VERSION_KEY, 1, None)


def annotate_selection(facets: dict, filters) -> dict:
    """Проставляет в фасеты текущий выбор пользователя.

    Шаблон не умеет доставать значение словаря по переменному ключу, а
    протаскивать эту логику в вёрстку — верный способ развести отображение и
    фактические фильтры. Поэтому выбор подмешивается здесь.

    Каждый раздел панели свёрнут по умолчанию, поэтому вместе с самим выбором
    считается число выбранных значений: по нему шаблон решает, какой раздел
    раскрыть и что показать на его заголовке.
    """
    brands = [{**item, "checked": item["slug"] in filters.brands} for item in facets["brands"]]
    machine_types = [
        {**item, "checked": item["slug"] in filters.machine_types}
        for item in facets["machine_types"]
    ]

    result = {
        "total": facets["total"],
        "brands": brands,
        "brands_selected": sum(1 for item in brands if item["checked"]),
        "machine_types": machine_types,
        "machine_types_selected": sum(1 for item in machine_types if item["checked"]),
        "numeric": [],
        "options": [],
        "boolean_groups": [],
    }

    for item in facets["numeric"]:
        low, high = filters.numeric.get(item["code"], (None, None))
        result["numeric"].append(
            {
                **item,
                "value_min": low,
                "value_max": high,
                "is_active": low is not None or high is not None,
            }
        )

    for item in facets["options"]:
        selected = filters.options.get(item["code"], [])
        values = [{**value, "checked": value["code"] in selected} for value in item["values"]]
        result["options"].append(
            {
                **item,
                "values": values,
                "selected_count": sum(1 for value in values if value["checked"]),
            }
        )

    # Булевы параметры собираются по своей группе из справочника: у каждого
    # она есть, и без неё они выпадали из панели строками без заголовка.
    # Группа, а не отдельный раздел на параметр: держать раскрывающийся
    # заголовок ради одной галочки — лишний клик, а вот общий заголовок
    # «Оснащение» осмыслен и растёт вместе с числом таких параметров.
    grouped: dict[str, list] = {}
    for item in facets["booleans"]:
        entry = {**item, "checked": bool(filters.booleans.get(item["code"]))}
        grouped.setdefault(item["group"], []).append(entry)

    result["boolean_groups"] = [
        {
            "name": name,
            "items": items,
            "selected_count": sum(1 for item in items if item["checked"]),
        }
        for name, items in grouped.items()
    ]

    return result
