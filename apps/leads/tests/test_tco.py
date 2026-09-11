"""Тесты калькулятора стоимости владения."""

from decimal import Decimal

import pytest

from apps.leads.services.tco import calculate_tco


def test_fuel_cost_is_consumption_times_price_times_hours():
    result = calculate_tco(hours_per_year=1000, fuel_consumption=20, fuel_price=60)
    assert result.fuel_cost_year == Decimal("1200000.00")


def test_depreciation_accounts_for_residual_value():
    """Амортизация линейная с остаточной стоимостью: 20% от цены не списывается."""
    result = calculate_tco(
        hours_per_year=1000,
        fuel_consumption=0,
        fuel_price=0,
        machine_price=10_000_000,
        lifetime_years=5,
        residual_share=Decimal("0.2"),
    )
    assert result.depreciation_year == Decimal("1600000.00")


def test_no_depreciation_without_price():
    result = calculate_tco(hours_per_year=1000, fuel_consumption=0, fuel_price=0)
    assert result.depreciation_year == Decimal("0.00")


def test_operator_cost_is_annualised():
    result = calculate_tco(
        hours_per_year=1000, fuel_consumption=0, fuel_price=0, operator_cost_month=100_000
    )
    assert result.operator_cost_year == Decimal("1200000.00")


def test_cost_per_hour_divides_total_by_hours():
    result = calculate_tco(
        hours_per_year=2000, fuel_consumption=10, fuel_price=60, maintenance_cost_year=200_000
    )
    assert result.total_cost_year == Decimal("1400000.00")
    assert result.cost_per_hour == Decimal("700.00")


def test_zero_hours_rejected():
    """Деление на ноль здесь означало бы бессмысленный результат, а не ошибку ввода."""
    with pytest.raises(ValueError, match="больше нуля"):
        calculate_tco(hours_per_year=0, fuel_consumption=10, fuel_price=60)


def test_lifetime_never_below_one_year():
    result = calculate_tco(
        hours_per_year=1000,
        fuel_consumption=0,
        fuel_price=0,
        machine_price=1_000_000,
        lifetime_years=0,
    )
    assert result.depreciation_year == Decimal("800000.00")


def test_as_dict_is_json_serialisable():
    import json

    result = calculate_tco(hours_per_year=1000, fuel_consumption=10, fuel_price=60)
    assert json.loads(json.dumps(result.as_dict()))["cost_per_hour"] == 600.0
