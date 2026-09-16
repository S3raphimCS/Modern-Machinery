"""Расчёт лизингового платежа.

В России лизинговые компании котируют сделку через **удорожание в год**, а не
через процентную ставку: клиенту называют «7% удорожания», и переплата
считается от финансируемой суммы за весь срок. Аннуитетная формула из
банковского кредита дала бы другие числа, и расчёт на сайте разошёлся бы с
тем, что клиенту скажут в лизинговой компании.

Расчёт вынесен в чистую функцию: он проверяется тестами без запросов, форм и
базы, а результат одинаково используется страницей, API и письмом.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class LeasingResult:
    """Разложение лизинговой сделки, в рублях."""

    price: Decimal
    advance: Decimal
    financed: Decimal
    overpayment: Decimal
    monthly_payment: Decimal
    total: Decimal

    def as_dict(self) -> dict:
        """Вид, пригодный для записи в JSON-поле заявки."""
        return {key: float(value) for key, value in asdict(self).items()}


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_leasing(
    *,
    price: Decimal | float | int,
    advance_percent: Decimal | float | int,
    months: int,
    markup_percent: Decimal | float | int,
) -> LeasingResult:
    """Считает аванс, переплату и ежемесячный платёж.

    Ежемесячный платёж — ориентир: реальный график лизинговая компания
    составляет сама, и последний платёж там обычно отличается на копейки
    из-за округления. Для оценки на сайте этого достаточно, и именно так
    сделку и обсуждают на первом разговоре.
    """
    price = Decimal(str(price))
    advance_percent = Decimal(str(advance_percent))
    markup_percent = Decimal(str(markup_percent))

    if price <= 0:
        raise ValueError("Стоимость техники должна быть больше нуля")
    if months <= 0:
        raise ValueError("Срок договора должен быть больше нуля")
    if not 0 <= advance_percent <= 100:
        raise ValueError("Аванс задаётся в процентах от нуля до ста")
    if markup_percent < 0:
        raise ValueError("Удорожание не может быть отрицательным")

    advance = price * advance_percent / Decimal("100")
    financed = price - advance
    # Удорожание годовое, поэтому умножается на число лет, а не на число
    # месяцев: срок вдвое длиннее даёт вдвое большую переплату.
    overpayment = financed * markup_percent / Decimal("100") * Decimal(months) / Decimal("12")
    monthly = (financed + overpayment) / Decimal(months)

    return LeasingResult(
        price=_money(price),
        advance=_money(advance),
        financed=_money(financed),
        overpayment=_money(overpayment),
        monthly_payment=_money(monthly),
        total=_money(price + overpayment),
    )
