"""Тесты API заявок и калькулятора стоимости владения."""

import time

import pytest
from django.core import mail, signing

from apps.leads.forms import FORM_TS_SALT
from apps.leads.models import Lead

pytestmark = pytest.mark.django_db


def payload(**overrides) -> dict:
    data = {
        "type": Lead.Type.PRICE,
        "name": "Снабженец",
        "phone": "+7 914 555-33-11",
        "consent": True,
    }
    data.update(overrides)
    return data


def post(client, data):
    return client.post("/api/v1/leads/", data, content_type="application/json")


def test_creates_lead(client, consent):
    response = post(client, payload())

    assert response.status_code == 201
    assert response.json()["created"] is True
    assert Lead.objects.count() == 1


def test_response_hides_personal_data(client, consent):
    """Ответ подтверждает приём и не более: возвращать ПДн обратно незачем."""
    body = post(client, payload()).json()
    assert set(body) == {"id", "type", "status", "created_at", "created"}


def test_duplicate_returns_created_false(client, consent):
    post(client, payload())
    response = post(client, payload())

    assert response.status_code == 201
    assert response.json()["created"] is False
    assert Lead.objects.count() == 1


def test_consent_is_required(client, consent):
    response = post(client, payload(consent=False))
    assert response.status_code == 400
    assert "consent" in response.json()


def test_contact_is_required(client, consent):
    response = post(client, payload(phone=""))
    assert response.status_code == 400
    assert Lead.objects.count() == 0


def test_honeypot_blocks_api_too(client, consent):
    """API не должен быть обходным путём для проверок HTML-формы."""
    response = post(client, payload(website="http://spam.example"))
    assert response.status_code == 400
    assert Lead.objects.count() == 0


def test_instant_submission_blocked(client, consent, settings):
    settings.LEAD_MIN_FORM_SECONDS = 3
    fresh = signing.dumps(time.time(), salt=FORM_TS_SALT)
    assert post(client, payload(form_ts=fresh)).status_code == 400


def test_machine_linked_by_slug(client, consent, machine):
    post(client, payload(machine=machine.slug))
    assert Lead.objects.get().machine == machine


def test_service_linked_by_slug(client, consent, db):
    from apps.services.factories import ServiceFactory

    service = ServiceFactory(slug="remont-gidravliki")
    post(client, payload(type=Lead.Type.SERVICE, service="remont-gidravliki"))
    assert Lead.objects.get().service == service


def test_notification_email_sent(client, consent, department, django_capture_on_commit_callbacks):
    """Письмо ставится в очередь только после коммита транзакции.

    Иначе воркер может взять задачу раньше, чем заявка окажется в базе, и не
    найти её. Поэтому тест явно выполняет колбэки коммита.
    """
    from apps.leads.factories import LeadRoutingRuleFactory

    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE, department=department, emails=["sales@modernmachinery.example"]
    )

    with django_capture_on_commit_callbacks(execute=True):
        post(client, payload())

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["sales@modernmachinery.example"]


def test_leads_cannot_be_listed(client, consent):
    """Заявки — персональные данные, наружу их не отдаём."""
    post(client, payload())
    assert client.get("/api/v1/leads/").status_code in {403, 405}


def test_unknown_lead_type_rejected(client, consent):
    assert post(client, payload(type="что-то своё")).status_code == 400


def test_tco_calculation(client):
    response = client.post(
        "/api/v1/tco/calculate/",
        {
            "hours_per_year": 1800,
            "fuel_consumption": 22,
            "fuel_price": 65,
            "maintenance_cost_year": 450000,
            "machine_price": 18000000,
            "lifetime_years": 7,
        },
        content_type="application/json",
    )

    data = response.json()
    assert response.status_code == 200
    assert data["fuel_cost_year"] == 2574000.0
    assert data["cost_per_hour"] > 0


def test_tco_rejects_zero_hours(client):
    response = client.post(
        "/api/v1/tco/calculate/",
        {"hours_per_year": 0, "fuel_consumption": 22, "fuel_price": 65},
        content_type="application/json",
    )
    assert response.status_code == 400
