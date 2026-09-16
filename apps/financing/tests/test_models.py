"""Тесты моделей раздела финансирования."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.financing.factories import LeasingPartnerFactory
from apps.financing.models import LeasingTerms

pytestmark = pytest.mark.django_db


def test_terms_are_created_on_first_use():
    terms = LeasingTerms.load()

    assert terms.pk is not None
    assert LeasingTerms.load().pk == terms.pk


def test_terms_are_a_singleton():
    LeasingTerms.load()

    with pytest.raises(ValidationError, match="уже заведены"):
        LeasingTerms().save()


def test_advance_cannot_exceed_hundred_percent():
    terms = LeasingTerms.load()
    terms.max_advance_percent = 120

    with pytest.raises(ValidationError, match="100"):
        terms.save()


def test_reversed_advance_range_rejected():
    """Ползунок с минимумом больше максимума не имеет смысла."""
    LeasingTerms.load()

    with pytest.raises(IntegrityError), transaction.atomic():
        LeasingTerms.objects.update(min_advance_percent=60, max_advance_percent=20)


def test_reversed_term_range_rejected():
    LeasingTerms.load()

    with pytest.raises(IntegrityError), transaction.atomic():
        LeasingTerms.objects.update(min_months=60, max_months=12)


def test_default_term_is_whole_years_within_range():
    """Срок по умолчанию — середина диапазона, округлённая до целых лет."""
    terms = LeasingTerms.load()
    terms.min_months = 12
    terms.max_months = 60
    terms.save()

    assert terms.default_months == 36
    assert terms.default_months % 12 == 0


def test_default_term_stays_inside_narrow_range():
    terms = LeasingTerms.load()
    terms.min_months = 13
    terms.max_months = 18
    terms.save()

    assert terms.min_months <= terms.default_months <= terms.max_months


def test_partner_ordering_and_str():
    second = LeasingPartnerFactory(name="Вторая", sort_order=20)
    first = LeasingPartnerFactory(name="Первая", sort_order=10)

    from apps.financing.models import LeasingPartner

    assert list(LeasingPartner.objects.all()) == [first, second]
    assert str(first) == "Первая"


def test_load_is_safe_when_called_twice():
    """На свежем сервере таблица пуста, и запросы идут параллельно.

    Раньше вторая попытка упиралась в проверку синглтона и роняла страницу
    ошибкой сервера прямо из шаблонного тега в плитке каталога.
    """
    first = LeasingTerms.load()
    second = LeasingTerms.load()

    assert first.pk == second.pk
    assert LeasingTerms.objects.count() == 1


def test_zero_term_is_rejected():
    """Срок в ноль месяцев уронил бы расчёт делением на ноль."""
    terms = LeasingTerms.load()
    terms.min_months = 0

    with pytest.raises(ValidationError):
        terms.save()


def test_default_term_rounds_up_from_the_middle():
    """Середина диапазона 0–60 приходится ровно на 2,5 года.

    Банковское округление вернуло бы 24 месяца вместо ожидаемых 36.
    """
    terms = LeasingTerms.load()
    terms.min_months = 1
    terms.max_months = 60
    terms.save()

    assert terms.default_months == 36


def test_saving_terms_resets_the_cached_copy():
    """Иначе плитка каталога до десяти минут считала бы по старым правилам."""
    from django.core.cache import cache

    from apps.financing.models import TERMS_CACHE_KEY
    from apps.financing.templatetags.financing import get_terms

    terms = LeasingTerms.load()
    get_terms()
    assert cache.get(TERMS_CACHE_KEY) is not None

    terms.default_markup_percent = 9
    terms.save()

    assert cache.get(TERMS_CACHE_KEY) is None
