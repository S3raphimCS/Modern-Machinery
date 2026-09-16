"""Тесты расчёта лизингового платежа.

В России лизинг котируют через удорожание в год, а не через процентную
ставку: лизинговая компания называет «7% удорожания», и клиент считает
переплату от финансируемой суммы. Аннуитет здесь дал бы другие числа и не
сошёлся бы с тем, что клиенту скажут в лизинговой компании.
"""

from decimal import Decimal

import pytest

from apps.financing.services.leasing import calculate_leasing


def test_control_example_from_spec():
    """Контрольный пример из дизайн-документа."""
    result = calculate_leasing(price=18_000_000, advance_percent=20, months=36, markup_percent=7)

    assert result.advance == Decimal("3600000.00")
    assert result.financed == Decimal("14400000.00")
    assert result.overpayment == Decimal("3024000.00")
    assert result.monthly_payment == Decimal("484000.00")
    assert result.total == Decimal("21024000.00")


def test_zero_advance_finances_full_price():
    result = calculate_leasing(price=1_000_000, advance_percent=0, months=12, markup_percent=10)

    assert result.advance == Decimal("0.00")
    assert result.financed == Decimal("1000000.00")
    assert result.overpayment == Decimal("100000.00")


def test_zero_markup_means_no_overpayment():
    """Рассрочка без удорожания: платёж — просто деление суммы на срок."""
    result = calculate_leasing(price=1_200_000, advance_percent=0, months=12, markup_percent=0)

    assert result.overpayment == Decimal("0.00")
    assert result.monthly_payment == Decimal("100000.00")
    assert result.total == Decimal("1200000.00")


def test_overpayment_grows_with_term():
    """Удорожание годовое, поэтому срок вдвое длиннее даёт вдвое больше переплаты."""
    short = calculate_leasing(price=1_000_000, advance_percent=0, months=12, markup_percent=10)
    long = calculate_leasing(price=1_000_000, advance_percent=0, months=24, markup_percent=10)

    assert long.overpayment == short.overpayment * 2


def test_advance_reduces_overpayment():
    """Переплата считается от финансируемой суммы, а не от полной стоимости."""
    without = calculate_leasing(price=1_000_000, advance_percent=0, months=12, markup_percent=10)
    with_advance = calculate_leasing(
        price=1_000_000, advance_percent=50, months=12, markup_percent=10
    )

    assert with_advance.overpayment == without.overpayment / 2


def test_single_month_term():
    result = calculate_leasing(price=120_000, advance_percent=0, months=1, markup_percent=12)

    assert result.overpayment == Decimal("1200.00")
    assert result.monthly_payment == Decimal("121200.00")


def test_full_advance_leaves_nothing_to_finance():
    """Стопроцентный аванс — это уже не лизинг, но считаться должно без ошибки."""
    result = calculate_leasing(price=1_000_000, advance_percent=100, months=12, markup_percent=10)

    assert result.financed == Decimal("0.00")
    assert result.overpayment == Decimal("0.00")
    assert result.monthly_payment == Decimal("0.00")


def test_total_always_equals_price_plus_overpayment():
    result = calculate_leasing(price=5_000_000, advance_percent=30, months=48, markup_percent=8)

    assert result.total == Decimal("5000000.00") + result.overpayment


def test_payments_add_up_to_total():
    """Аванс плюс все платежи должны сойтись с итогом — иначе расчёт врёт клиенту."""
    result = calculate_leasing(price=3_000_000, advance_percent=25, months=24, markup_percent=9)

    assert result.advance + result.monthly_payment * 24 == result.total


@pytest.mark.parametrize("months", [0, -12])
def test_term_must_be_positive(months):
    with pytest.raises(ValueError, match="Срок"):
        calculate_leasing(price=1_000_000, advance_percent=0, months=months, markup_percent=10)


def test_price_must_be_positive():
    with pytest.raises(ValueError, match="Стоимость"):
        calculate_leasing(price=0, advance_percent=0, months=12, markup_percent=10)


@pytest.mark.parametrize("advance", [-1, 101])
def test_advance_must_be_a_percentage(advance):
    with pytest.raises(ValueError, match="Аванс"):
        calculate_leasing(price=1_000_000, advance_percent=advance, months=12, markup_percent=10)


def test_result_is_json_serialisable():
    """Расчёт сохраняется в заявке, а Decimal в JSON не укладывается."""
    import json

    result = calculate_leasing(price=1_000_000, advance_percent=20, months=12, markup_percent=10)
    assert json.loads(json.dumps(result.as_dict()))["monthly_payment"] > 0
