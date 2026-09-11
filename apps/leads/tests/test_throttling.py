"""Тесты дросселирования на создании заявки.

Ручка создания заявки — единственная публичная точка записи в базу. Проверяется,
что лимит действительно останавливает поток и что его нельзя обойти, перейдя с
API на обычную HTML-форму: корзина у них общая.
"""

import time

import pytest
from django.core import signing
from django.test import override_settings

from apps.leads.forms import FORM_TS_SALT
from apps.leads.models import Lead
from apps.leads.throttling import (
    LeadBurstRateThrottle,
    LeadRateThrottle,
    check_lead_throttles,
)

pytestmark = pytest.mark.django_db


def api_payload(**overrides) -> dict:
    data = {
        "type": Lead.Type.PRICE,
        "name": "Снабженец",
        "phone": "+7 914 555-33-11",
        "consent": True,
        "message": "",
    }
    data.update(overrides)
    return data


def form_payload(index: int = 0) -> dict:
    return {
        "name": f"Клиент {index}",
        "phone": f"+7 914 000-00-{index:02d}",
        "consent": "1",
        "website": "",
        "form_ts": signing.dumps(time.time() - 10, salt=FORM_TS_SALT),
    }


@override_settings(LEAD_THROTTLE_RATE="3/hour", LEAD_THROTTLE_BURST_RATE="10/min")
def test_api_stops_flood_after_limit(client, consent):
    """Четвёртая заявка за час с одного адреса не проходит."""
    statuses = []
    for index in range(4):
        response = client.post(
            "/api/v1/leads/",
            api_payload(name=f"Клиент {index}", phone=f"+7 914 000-00-{index:02d}"),
            content_type="application/json",
        )
        statuses.append(response.status_code)

    assert statuses[:3] == [201, 201, 201]
    assert statuses[3] == 429
    assert Lead.objects.count() == 3


@override_settings(LEAD_THROTTLE_RATE="100/hour", LEAD_THROTTLE_BURST_RATE="2/min")
def test_burst_bucket_catches_spike(client, consent):
    """Короткое окно ловит всплеск, который укладывается в часовой лимит."""
    statuses = [
        client.post(
            "/api/v1/leads/",
            api_payload(name=f"К{index}", phone=f"+7 914 111-11-{index:02d}"),
            content_type="application/json",
        ).status_code
        for index in range(3)
    ]
    assert statuses == [201, 201, 429]


@override_settings(LEAD_THROTTLE_RATE="2/hour", LEAD_THROTTLE_BURST_RATE="10/min")
def test_html_form_shares_bucket_with_api(client, consent):
    """Переход с API на HTML-форму не сбрасывает счётчик.

    Иначе лимит на ручке был бы декорацией: тот же поток пошёл бы через форму.
    """
    first = client.post("/api/v1/leads/", api_payload(), content_type="application/json")
    second = client.post("/zayavka/price/", form_payload(1))
    third = client.post("/zayavka/price/", form_payload(2))

    assert first.status_code == 201
    assert second.status_code == 200
    assert third.status_code == 429
    assert "Слишком много заявок" in third.content.decode()


@override_settings(LEAD_THROTTLE_RATE="1/hour", LEAD_THROTTLE_BURST_RATE="10/min")
def test_throttle_counts_per_ip(client, consent):
    """Лимит считается по адресу, поэтому другой клиент не заблокирован."""
    assert (
        client.post("/api/v1/leads/", api_payload(), content_type="application/json").status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/leads/",
            api_payload(name="Другой", phone="+7 914 222-22-22"),
            content_type="application/json",
        ).status_code
        == 429
    )

    other = client.post(
        "/api/v1/leads/",
        api_payload(name="Из другой сети", phone="+7 914 333-33-33"),
        content_type="application/json",
        REMOTE_ADDR="10.20.30.40",
    )
    assert other.status_code == 201


@override_settings(LEAD_THROTTLE_RATE="1/hour", LEAD_THROTTLE_BURST_RATE="1/min")
def test_check_lead_throttles_helper(rf):
    request = rf.post("/zayavka/price/")
    request.META["REMOTE_ADDR"] = "127.0.0.55"

    assert check_lead_throttles(request) is True
    assert check_lead_throttles(request) is False


def test_throttle_key_built_from_ip(rf):
    request = rf.post("/api/v1/leads/")
    request.META["REMOTE_ADDR"] = "203.0.113.7"

    for throttle_class in (LeadRateThrottle, LeadBurstRateThrottle):
        throttle = throttle_class()
        assert "203.0.113.7" in throttle.get_cache_key(request)
