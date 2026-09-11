"""Калькулятор стоимости владения техникой.

Простой лид-магнит из раздела 3.2 плана: посетитель вводит наработку, расход и
стоимость обслуживания, получает стоимость часа работы машины. Расчёт вынесен в
чистую функцию, чтобы его можно было проверить тестами без запросов и форм.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class TcoResult:
    """Разложение стоимости владения по статьям, в рублях."""

    fuel_cost_year: Decimal
    maintenance_cost_year: Decimal
    depreciation_year: Decimal
    operator_cost_year: Decimal
    total_cost_year: Decimal
    cost_per_hour: Decimal

    def as_dict(self) -> dict:
        return {key: float(value) for key, value in asdict(self).items()}


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_tco(
    *,
    hours_per_year: Decimal | int,
    fuel_consumption: Decimal | float,
    fuel_price: Decimal | float,
    maintenance_cost_year: Decimal | float = 0,
    machine_price: Decimal | float = 0,
    lifetime_years: int = 7,
    residual_share: Decimal | float = Decimal("0.2"),
    operator_cost_month: Decimal | float = 0,
) -> TcoResult:
    """Считает годовую стоимость владения и стоимость машино-часа.

    Амортизация линейная с учётом остаточной стоимости — этого достаточно для
    оценки на сайте; точная финансовая модель здесь была бы ложной точностью.
    """
    hours = Decimal(str(hours_per_year))
    if hours <= 0:
        raise ValueError("Наработка за год должна быть больше нуля")
    lifetime = max(int(lifetime_years), 1)

    fuel = Decimal(str(fuel_consumption)) * Decimal(str(fuel_price)) * hours
    maintenance = Decimal(str(maintenance_cost_year))
    price = Decimal(str(machine_price))
    residual = price * Decimal(str(residual_share))
    depreciation = (price - residual) / Decimal(lifetime) if price else Decimal("0")
    operator = Decimal(str(operator_cost_month)) * Decimal("12")

    total = fuel + maintenance + depreciation + operator
    return TcoResult(
        fuel_cost_year=_money(fuel),
        maintenance_cost_year=_money(maintenance),
        depreciation_year=_money(depreciation),
        operator_cost_year=_money(operator),
        total_cost_year=_money(total),
        cost_per_hour=_money(total / hours),
    )
