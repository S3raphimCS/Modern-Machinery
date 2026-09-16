"""Тесты единой точки создания заявки."""

import datetime

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.leads.models import Lead, LeadEvent
from apps.leads.services import antispam
from apps.leads.services.creation import collect_request_meta, create_lead

pytestmark = pytest.mark.django_db


def base_data(**overrides) -> dict:
    data = {"type": Lead.Type.PRICE, "name": "Иванов", "phone": "+7 914 000-11-22"}
    data.update(overrides)
    return data


def test_creates_lead_with_event(consent):
    lead, created = create_lead(data=base_data())

    assert created is True
    assert Lead.objects.count() == 1
    assert lead.events.filter(kind=LeadEvent.Kind.CREATED).exists()


def test_links_active_consent_version(consent):
    """Через год нужно доказать, с каким текстом согласился посетитель."""
    lead, _ = create_lead(data=base_data())

    assert lead.consent == consent
    assert lead.consent_at is not None


def test_consent_not_linked_when_not_given(consent):
    lead, _ = create_lead(data=base_data(), consent_given=False)
    assert lead.consent is None


@override_settings(LEAD_RETENTION_DAYS=30)
def test_sets_retention_deadline(consent):
    """Срок хранения ПДн проставляется сразу — иначе непонятно, что чистить."""
    lead, _ = create_lead(data=base_data())
    expected = (timezone.now() + datetime.timedelta(days=30)).date()
    assert lead.purge_after == expected


def test_collects_request_metadata(rf, consent):
    # Метки приходят из cookie: форма постится на адрес без параметров, и
    # прежняя версия этого теста дописывала их прямо в адрес отправки —
    # ситуация, которой не бывает, из-за чего дефект и не был замечен.
    from django.core import signing

    from apps.leads.middleware import COOKIE_NAME

    request = rf.post("/zayavka/price/")
    request.COOKIES[COOKIE_NAME] = signing.dumps({"utm_source": "yandex", "utm_campaign": "khv"})
    request.META["HTTP_REFERER"] = "https://example.com/tehnika/"
    request.META["HTTP_USER_AGENT"] = "Mozilla/5.0"
    request.META["REMOTE_ADDR"] = "203.0.113.9"

    lead, _ = create_lead(data=base_data(), request=request)

    assert lead.utm == {"utm_source": "yandex", "utm_campaign": "khv"}
    assert lead.referrer == "https://example.com/tehnika/"
    assert lead.ip_address == "203.0.113.9"
    assert lead.user_agent == "Mozilla/5.0"


def test_collect_meta_without_request():
    assert collect_request_meta(None) == {}


def test_uses_forwarded_ip_behind_proxy(rf, consent):
    """Приложение стоит за nginx, поэтому адрес берётся из заголовка."""
    request = rf.post("/zayavka/price/")
    request.META["HTTP_X_FORWARDED_FOR"] = "198.51.100.5, 10.0.0.1"

    lead, _ = create_lead(data=base_data(), request=request)
    assert lead.ip_address == "198.51.100.5"


def test_duplicate_within_window_returns_existing(consent):
    """Повторная отправка не плодит дубли, но и не выглядит ошибкой для клиента."""
    first, created_first = create_lead(data=base_data())
    second, created_second = create_lead(data=base_data())

    assert created_first is True
    assert created_second is False
    assert first.pk == second.pk
    assert Lead.objects.count() == 1


def test_different_content_is_not_duplicate(consent):
    create_lead(data=base_data())
    _, created = create_lead(data=base_data(name="Петров"))
    assert created is True
    assert Lead.objects.count() == 2


def test_fingerprint_includes_ip():
    """Две компании могут прислать одинаково выглядящую заявку — глушить нельзя."""
    common = {
        "lead_type": "price",
        "name": "Иванов",
        "phone": "+7 914 000-11-22",
        "email": "",
        "message": "",
    }
    first = antispam.build_fingerprint(**common, ip="203.0.113.1")
    second = antispam.build_fingerprint(**common, ip="203.0.113.2")
    assert first != second


def test_fingerprint_ignores_case_and_spaces():
    left = antispam.build_fingerprint(
        lead_type="price", name=" Иванов ", phone="1", email="A@B.RU", message="Нужен ковш", ip=None
    )
    right = antispam.build_fingerprint(
        lead_type="price", name="иванов", phone="1", email="a@b.ru", message="нужен ковш", ip=None
    )
    assert left == right


def test_dedupe_ignores_deleted_lead(consent):
    """Если заявку удалили из базы, повтор должен создать новую."""
    lead, _ = create_lead(data=base_data())
    lead_pk = lead.pk
    Lead.objects.filter(pk=lead_pk).delete()

    _, created = create_lead(data=base_data())
    assert created is True


def test_department_assigned_from_routing_rule(consent, department, machine):
    from apps.leads.factories import LeadRoutingRuleFactory

    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE, department=department, emails=["sales@modernmachinery.example"]
    )
    lead, _ = create_lead(data=base_data(machine=machine))
    assert lead.department == department
