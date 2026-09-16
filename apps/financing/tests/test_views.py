"""Тесты страницы лизинга."""

import pytest
from django.urls import reverse

from apps.financing.factories import LeasingPartnerFactory
from apps.financing.models import LeasingTerms
from apps.leads.models import Lead

pytestmark = pytest.mark.django_db

CALC_INPUT = {
    "price": "18000000",
    "advance_percent": "20",
    "months": "36",
    "markup_percent": "7",
}


@pytest.fixture
def terms(db):
    terms = LeasingTerms.load()
    terms.min_advance_percent = 10
    terms.max_advance_percent = 49
    terms.min_months = 12
    terms.max_months = 60
    terms.save()
    return terms


def test_page_renders(client, branch, terms):
    response = client.get(reverse("financing:leasing"))

    assert response.status_code == 200
    assert response.context["terms"] == terms


def test_page_lists_active_partners(client, branch, terms):
    LeasingPartnerFactory(name="Первая", is_active=True)
    LeasingPartnerFactory(name="Скрытая", is_active=False)

    content = client.get(reverse("financing:leasing")).content.decode()

    assert "Первая" in content
    assert "Скрытая" not in content


def test_calculation_returns_control_example(client, branch, terms):
    response = client.post(reverse("financing:leasing"), CALC_INPUT)
    result = response.context["result"]

    assert response.status_code == 200
    assert int(result.monthly_payment) == 484_000
    assert int(result.overpayment) == 3_024_000


def test_calculation_via_htmx_returns_fragment(client, branch, terms):
    response = client.post(reverse("financing:leasing"), CALC_INPUT, HTTP_HX_REQUEST="true")
    names = [t.name for t in response.templates]

    assert "financing/partials/result.html" in names
    assert "base.html" not in names


def test_advance_outside_terms_is_rejected(client, branch, terms):
    """Границы калькулятора задаются условиями в админке, а не в коде."""
    response = client.post(reverse("financing:leasing"), {**CALC_INPUT, "advance_percent": "5"})

    assert response.status_code == 400
    assert "advance_percent" in response.context["form"].errors


def test_term_outside_range_is_rejected(client, branch, terms):
    response = client.post(reverse("financing:leasing"), {**CALC_INPUT, "months": "120"})

    assert response.status_code == 400


def test_calculation_without_contacts_creates_no_lead(client, branch, terms, consent):
    client.post(reverse("financing:leasing"), CALC_INPUT)

    assert Lead.objects.count() == 0


def test_contacts_turn_calculation_into_a_lead(client, branch, terms, consent):
    """Расчёт сохраняется целиком: менеджер продолжает разговор с тех же чисел."""
    response = client.post(
        reverse("financing:leasing"),
        {**CALC_INPUT, "name": "Иванов", "phone": "+7 914 000-11-22"},
    )

    lead = Lead.objects.get()
    assert lead.type == Lead.Type.LEASING
    assert lead.payload["input"]["price"] == 18_000_000
    assert lead.payload["result"]["monthly_payment"] == 484_000
    assert response.context["lead_saved"] is True


def test_terms_shown_in_page(client, branch, terms):
    content = client.get(reverse("financing:leasing")).content.decode()

    assert f"от {terms.min_advance_percent}%" in content
    assert f"до {terms.max_months} мес" in content


def test_machine_card_shows_monthly_payment(client, machine, terms):
    """Платёж рядом с ценой продаёт сильнее, чем страница с условиями."""
    from django.core.cache import cache

    machine.price = 18_000_000
    machine.is_price_on_request = False
    machine.save()
    terms.min_advance_percent = 20
    terms.min_months = 36
    terms.max_months = 36
    terms.save()
    cache.clear()

    content = client.get(machine.get_absolute_url()).content.decode()

    assert "в лизинг" in content
    assert "484" in content


def test_no_monthly_payment_when_price_on_request(client, machine, terms):
    machine.price = 18_000_000
    machine.is_price_on_request = True
    machine.save()

    assert "в лизинг" not in client.get(machine.get_absolute_url()).content.decode()
