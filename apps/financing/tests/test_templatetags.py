"""Тесты вывода лизингового платежа на карточке техники."""

import pytest
from django.core.cache import cache
from django.template import Context

from apps.financing.models import LeasingTerms
from apps.financing.templatetags.financing import leasing_monthly as _leasing_monthly


def leasing_monthly(price, context=None):
    """Вызов тега с пустым контекстом: в шаблоне его передаёт движок."""
    return _leasing_monthly(context if context is not None else Context(), price)


pytestmark = pytest.mark.django_db


def test_monthly_payment_calculated_from_terms():
    terms = LeasingTerms.load()
    terms.min_advance_percent = 20
    terms.min_months = 36
    terms.max_months = 36
    terms.default_markup_percent = 7
    terms.save()
    cache.clear()

    # Контрольный пример: 18 млн, аванс 20%, 36 месяцев, удорожание 7%.
    assert leasing_monthly(18_000_000) == 484_000


def test_no_payment_without_price():
    """У большинства позиций цена «по запросу» — показывать платёж не от чего."""
    LeasingTerms.load()

    assert leasing_monthly(None) is None
    assert leasing_monthly(0) is None


def test_terms_are_cached_between_calls(django_assert_max_num_queries):
    LeasingTerms.load()
    cache.clear()

    leasing_monthly(1_000_000)
    with django_assert_max_num_queries(0):
        leasing_monthly(2_000_000)
        leasing_monthly(3_000_000)


def test_terms_are_read_once_per_page(django_assert_max_num_queries):
    """Плитка зовёт тег на каждой карточке — условия берутся из контекста.

    Без этого при выключенном кэше получался запрос к базе на каждую
    карточку списка.
    """
    LeasingTerms.load()
    cache.clear()
    context = Context()

    leasing_monthly(1_000_000, context)
    with django_assert_max_num_queries(0):
        for _ in range(12):
            leasing_monthly(2_000_000, context)
