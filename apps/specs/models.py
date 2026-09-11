"""Справочник параметров и значения характеристик техники.

Решение из раздела 6.1 плана: нормализованная таблица `MachineSpec` — источник
истины и основа фильтров, а денормализованный `Machine.specs_cache` — готовый к
рендеру снимок для плитки каталога. Чистый JSONB не дал бы диапазонных фильтров,
чистый EAV потребовал бы JOIN на каждую характеристику при выводе списка.
"""

from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import SortableMixin


class SpecGroup(SortableMixin):
    """Группа параметров: Двигатель, Габариты, Рабочее оборудование, Массы."""

    code = models.SlugField("Код", max_length=60, unique=True)
    name = models.CharField("Название", max_length=120)

    class Meta:
        verbose_name = "Группа характеристик"
        verbose_name_plural = "Группы характеристик"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class SpecKey(SortableMixin):
    """Справочный параметр.

    Единица измерения, тип значения и признак фильтруемости живут здесь, а не в
    строке значения. Без справочника через год в базе окажутся «Мощность»,
    «Мощность двигателя», «Мощность, кВт» и «мощность двиг.» как четыре разных
    параметра, и фильтр не построить ни по одному из них.
    """

    class ValueType(models.TextChoices):
        NUMBER = "number", "Число"
        STRING = "string", "Строка"
        BOOL = "bool", "Да/Нет"
        OPTION = "option", "Значение из списка"

    code = models.SlugField("Код", max_length=80, unique=True)
    name = models.CharField("Название", max_length=160)
    group = models.ForeignKey(
        SpecGroup, verbose_name="Группа", on_delete=models.PROTECT, related_name="keys"
    )
    unit = models.CharField("Единица измерения", max_length=32, blank=True)
    value_type = models.CharField(
        "Тип значения", max_length=10, choices=ValueType.choices, default=ValueType.NUMBER
    )

    machine_types = models.ManyToManyField(
        "catalog.MachineType", verbose_name="Типы техники", blank=True, related_name="spec_keys"
    )

    is_filterable = models.BooleanField("Участвует в фильтрах", default=False, db_index=True)
    is_in_card = models.BooleanField("Выводить в плитке каталога", default=False)
    is_comparable = models.BooleanField("Участвует в сравнении", default=True)
    decimals = models.PositiveSmallIntegerField("Знаков после запятой", default=0)

    # Синонимы из источников данных: по ним импорт сам находит нужный параметр,
    # поэтому повторные прогоны идемпотентны.
    aliases = ArrayField(
        models.CharField(max_length=160),
        verbose_name="Синонимы",
        default=list,
        blank=True,
    )

    class Meta:
        verbose_name = "Параметр"
        verbose_name_plural = "Справочник параметров"
        ordering = ["group__sort_order", "sort_order", "name"]

    def __str__(self) -> str:
        return f"{self.name}, {self.unit}" if self.unit else self.name

    def format_value(self, spec: "MachineSpec") -> str:
        """Готовит значение к выводу с учётом типа и числа знаков."""
        if spec.value_bool is not None:
            return "Есть" if spec.value_bool else "Нет"
        if spec.value_option_id:
            return spec.value_option.name
        if spec.value_num is not None:
            low = f"{spec.value_num:.{self.decimals}f}"
            if spec.value_num_max is not None:
                return f"{low}–{spec.value_num_max:.{self.decimals}f}"
            return low
        return spec.value_str


class SpecOption(SortableMixin):
    """Допустимое значение параметра типа «список»."""

    spec_key = models.ForeignKey(
        SpecKey, verbose_name="Параметр", on_delete=models.CASCADE, related_name="options"
    )
    code = models.SlugField("Код", max_length=60)
    name = models.CharField("Название", max_length=160)

    class Meta:
        verbose_name = "Значение параметра"
        verbose_name_plural = "Значения параметров"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["spec_key", "code"], name="specoption_unique_code")
        ]

    def __str__(self) -> str:
        return self.name


class MachineSpec(models.Model):
    """Значение параметра у конкретной модели техники."""

    machine = models.ForeignKey(
        "catalog.Machine", verbose_name="Техника", on_delete=models.CASCADE, related_name="specs"
    )
    spec_key = models.ForeignKey(
        SpecKey, verbose_name="Параметр", on_delete=models.PROTECT, related_name="values"
    )

    value_num = models.DecimalField("Число", max_digits=14, decimal_places=4, null=True, blank=True)
    value_str = models.CharField("Строка", max_length=255, blank=True)
    value_bool = models.BooleanField("Да/Нет", null=True, blank=True)
    value_option = models.ForeignKey(
        SpecOption,
        verbose_name="Значение из списка",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    # У экскаваторов половина параметров — диапазоны («глубина копания 6,6–7,4 м»).
    # Без отдельного верхнего значения диапазон уехал бы в строку и выпал из фильтров.
    value_num_max = models.DecimalField(
        "Число, верхняя граница", max_digits=14, decimal_places=4, null=True, blank=True
    )
    raw_value = models.CharField("Исходное значение", max_length=255, blank=True)

    class Meta:
        verbose_name = "Характеристика"
        verbose_name_plural = "Характеристики"
        ordering = ["spec_key__group__sort_order", "spec_key__sort_order"]
        constraints = [
            models.UniqueConstraint(fields=["machine", "spec_key"], name="machinespec_unique_key"),
            # Ровно одно значение из четырёх: иначе непонятно, что показывать
            # и по чему фильтровать.
            models.CheckConstraint(
                name="machinespec_exactly_one_value",
                condition=(
                    models.Q(
                        value_num__isnull=False,
                        value_str="",
                        value_bool__isnull=True,
                        value_option__isnull=True,
                    )
                    | models.Q(
                        value_num__isnull=True,
                        value_num_max__isnull=True,
                        value_bool__isnull=True,
                        value_option__isnull=True,
                    )
                    & ~models.Q(value_str="")
                    | models.Q(
                        value_bool__isnull=False,
                        value_num__isnull=True,
                        value_num_max__isnull=True,
                        value_str="",
                        value_option__isnull=True,
                    )
                    | models.Q(
                        value_option__isnull=False,
                        value_num__isnull=True,
                        value_num_max__isnull=True,
                        value_str="",
                        value_bool__isnull=True,
                    )
                ),
            ),
            # Верхняя граница диапазона осмысленна только вместе с нижней и
            # обязана быть не меньше неё.
            models.CheckConstraint(
                name="machinespec_range_ordered",
                condition=(
                    models.Q(value_num_max__isnull=True)
                    | models.Q(value_num__isnull=False, value_num_max__gte=models.F("value_num"))
                ),
            ),
        ]
        indexes = [
            models.Index(fields=["spec_key", "value_num"], name="spec_num_filter_idx"),
            models.Index(fields=["spec_key", "value_option"], name="spec_opt_filter_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.spec_key}: {self.display_value}"

    @property
    def display_value(self) -> str:
        return self.spec_key.format_value(self)
