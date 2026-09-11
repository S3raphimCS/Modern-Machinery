"""Фильтрация каталога по характеристикам.

Фильтр по нескольким характеристикам сделан через `EXISTS`-подзапросы, а не через
цепочку JOIN к `MachineSpec`. На сотнях машин разница по времени незаметна, зато
план запроса остаётся предсказуемым и не размножает строки при нескольких
условиях подряд.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db.models import Exists, OuterRef, Q, QuerySet
from django.db.models.functions import Coalesce

from apps.specs.models import MachineSpec, SpecKey

# Префикс query-параметров характеристик: ?spec_engine_power_min=150
SPEC_PREFIX = "spec_"

SORT_OPTIONS = {
    "default": ["sort_order", "name"],
    "name": ["name"],
    "-name": ["-name"],
    "price": ["price", "name"],
    "-price": ["-price", "name"],
    "new": ["-created_at"],
}


@dataclass
class CatalogFilters:
    """Разобранные параметры фильтрации каталога."""

    query: str = ""
    brands: list[str] = field(default_factory=list)
    machine_types: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    in_stock_only: bool = False
    sort: str = "default"
    # code -> (min, max) для числовых параметров
    numeric: dict[str, tuple[Decimal | None, Decimal | None]] = field(default_factory=dict)
    # code -> список кодов вариантов для параметров-списков
    options: dict[str, list[str]] = field(default_factory=dict)
    # code -> True/False для булевых параметров
    booleans: dict[str, bool] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not any(
            [
                self.query,
                self.brands,
                self.machine_types,
                self.categories,
                self.in_stock_only,
                self.numeric,
                self.options,
                self.booleans,
            ]
        )

    @property
    def active_count(self) -> int:
        """Сколько условий выбрано.

        Панель фильтров по умолчанию свёрнута, поэтому число выводится прямо на
        кнопке: иначе посетитель не поймёт, почему в каталоге всего три позиции.
        Диапазон «от и до» по одному параметру считается одним условием — так,
        как его воспринимает человек.
        """
        count = len(self.brands) + len(self.machine_types) + len(self.categories)
        count += len(self.numeric) + len(self.booleans)
        count += sum(len(values) for values in self.options.values())
        if self.in_stock_only:
            count += 1
        return count


def _to_decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(str(raw).replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_filters(params, spec_keys: list[SpecKey] | None = None) -> CatalogFilters:
    """Разбирает query-параметры запроса в структуру фильтров.

    Некорректные значения молча игнорируются: посетитель не должен получать 500
    из-за того, что руками поправил ссылку.
    """
    if spec_keys is None:
        spec_keys = list(SpecKey.objects.filter(is_filterable=True))
    keys_by_code = {key.code: key for key in spec_keys}

    filters = CatalogFilters(
        query=(params.get("q") or "").strip(),
        brands=[v for v in params.getlist("brand") if v],
        machine_types=[v for v in params.getlist("type") if v],
        categories=[v for v in params.getlist("category") if v],
        in_stock_only=params.get("in_stock") in {"1", "true", "on", "yes"},
    )

    sort = params.get("sort") or "default"
    filters.sort = sort if sort in SORT_OPTIONS else "default"

    for name in params:
        if not name.startswith(SPEC_PREFIX):
            continue
        body = name[len(SPEC_PREFIX) :]
        if body.endswith("_min") or body.endswith("_max"):
            code, bound = body[:-4], body[-3:]
            key = keys_by_code.get(code)
            if key is None or key.value_type != SpecKey.ValueType.NUMBER:
                continue
            value = _to_decimal(params.get(name))
            if value is None:
                continue
            low, high = filters.numeric.get(code, (None, None))
            filters.numeric[code] = (value, high) if bound == "min" else (low, value)
            continue

        key = keys_by_code.get(body)
        if key is None:
            continue
        values = [v for v in params.getlist(name) if v]
        if not values:
            continue
        if key.value_type == SpecKey.ValueType.BOOL:
            filters.booleans[body] = values[0] in {"1", "true", "on", "yes"}
        elif key.value_type == SpecKey.ValueType.OPTION:
            filters.options[body] = values

    return filters


def _spec_exists(code: str, condition: Q) -> Exists:
    """Собирает `EXISTS`-подзапрос по характеристике конкретной машины.

    Аннотация `effective_max` нужна диапазонным характеристикам: у одиночного
    значения верхней границы нет, и сравнивать приходится с самим значением.
    """
    return Exists(
        MachineSpec.objects.annotate(effective_max=Coalesce("value_num_max", "value_num")).filter(
            condition, machine=OuterRef("pk"), spec_key__code=code
        )
    )


def apply_filters(queryset: QuerySet, filters: CatalogFilters) -> QuerySet:
    """Применяет разобранные фильтры к набору машин."""
    if filters.query:
        queryset = queryset.search(filters.query)
    if filters.brands:
        queryset = queryset.filter(brand__slug__in=filters.brands)
    if filters.machine_types:
        queryset = queryset.filter(machine_type__slug__in=filters.machine_types)
    if filters.categories:
        queryset = queryset.filter(categories__slug__in=filters.categories).distinct()
    if filters.in_stock_only:
        queryset = queryset.filter(
            stocks__status__in=["in_stock", "low"],
        ).distinct()

    for code, (low, high) in filters.numeric.items():
        if low is not None:
            # Для диапазонной характеристики граница «от» сравнивается с верхним
            # значением: машина с глубиной копания 6,6–7,4 м подходит под «от 7».
            queryset = queryset.filter(
                _spec_exists(
                    code,
                    Q(effective_max__gte=low),
                )
            )
        if high is not None:
            queryset = queryset.filter(_spec_exists(code, Q(value_num__lte=high)))

    for code, option_codes in filters.options.items():
        queryset = queryset.filter(_spec_exists(code, Q(value_option__code__in=option_codes)))

    for code, value in filters.booleans.items():
        queryset = queryset.filter(_spec_exists(code, Q(value_bool=value)))

    if not filters.query:
        queryset = queryset.order_by(*SORT_OPTIONS[filters.sort])
    return queryset
