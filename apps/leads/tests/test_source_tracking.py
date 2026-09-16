"""Тесты запоминания источника перехода."""

import pytest
from django.core import signing
from django.urls import reverse

from apps.leads.middleware import COOKIE_NAME, MAX_VALUE_LENGTH, read_marks
from apps.leads.models import Lead
from apps.leads.services.creation import collect_request_meta, create_lead

pytestmark = pytest.mark.django_db


def marks_from(response) -> dict:
    return signing.loads(response.cookies[COOKIE_NAME].value)


def test_campaign_marks_are_remembered(client, branch):
    response = client.get("/?utm_source=yandex&utm_medium=cpc&utm_campaign=khv-excavators")

    assert marks_from(response) == {
        "utm_source": "yandex",
        "utm_medium": "cpc",
        "utm_campaign": "khv-excavators",
    }


def test_direct_click_id_is_remembered(client, branch):
    """Без `yclid` заявку не связать с кампанией в Яндекс.Директе."""
    response = client.get("/?yclid=12345678901234567")

    assert marks_from(response)["yclid"] == "12345678901234567"


def test_internal_navigation_keeps_the_source(client, branch):
    """Переход по сайту не должен затирать рекламный источник."""
    client.get("/?utm_source=yandex")
    response = client.get("/tehnika/")

    assert COOKIE_NAME not in response.cookies


def test_new_campaign_overwrites_the_previous_one(client, branch):
    """Последнее касание, а не первое: иначе первая реклама присвоит себе всё."""
    client.get("/?utm_source=yandex")
    response = client.get("/?utm_source=2gis")

    assert marks_from(response)["utm_source"] == "2gis"


def test_marks_reach_the_lead(client, branch, consent, department):
    """Ради этого всё и делается: форма постится на адрес без параметров."""
    client.get("/?utm_source=yandex&utm_campaign=khv&yclid=42")

    client.post(
        reverse("content:lead-create", args=["price"]),
        {"name": "Иван", "phone": "+7 914 771-05-42", "consent": "1"},
    )

    lead = Lead.objects.get()
    assert lead.utm == {"utm_source": "yandex", "utm_campaign": "khv", "yclid": "42"}


def test_unknown_parameters_are_ignored(client, branch):
    """Белый список: значение доезжает до письма менеджеру."""
    response = client.get("/?utm_source=yandex&password=secret")

    assert "password" not in marks_from(response)


def test_long_value_is_truncated(client, branch):
    response = client.get("/?utm_campaign=" + "a" * 500)

    assert len(marks_from(response)["utm_campaign"]) == MAX_VALUE_LENGTH


def test_forged_cookie_does_not_break_the_form(client, branch, consent, department):
    """Испорченная подпись не повод ронять заявку: форма важнее аналитики."""
    client.cookies[COOKIE_NAME] = "eyJ1dG1fc291cmNlIjoieWFuZGV4In0:forged"

    response = client.post(
        reverse("content:lead-create", args=["price"]),
        {"name": "Иван", "phone": "+7 914 771-05-42", "consent": "1"},
    )

    assert response.status_code == 200
    assert Lead.objects.get().utm == {}


def test_forged_cookie_reads_as_empty(rf):
    request = rf.get("/")
    request.COOKIES[COOKIE_NAME] = signing.dumps({"utm_source": "yandex"}) + "x"

    assert read_marks(request) == {}


def test_admin_does_not_get_the_cookie(admin_client, branch):
    response = admin_client.get("/admin/?utm_source=yandex")

    assert COOKIE_NAME not in response.cookies


def test_non_html_answer_does_not_get_the_cookie(client, branch):
    response = client.get("/robots.txt?utm_source=yandex")

    assert COOKIE_NAME not in response.cookies


def test_api_request_still_reads_parameters(rf):
    """У заявок из API cookie нет, но параметры могут прийти напрямую."""
    request = rf.post("/api/v1/leads/?utm_source=partner")

    assert collect_request_meta(request)["utm"] == {"utm_source": "partner"}


def test_lead_without_request_has_no_marks(consent, department):
    lead, _ = create_lead(
        data={"type": Lead.Type.PRICE, "name": "Иван", "phone": "+7 914 771-05-42"},
        request=None,
    )

    assert lead.utm == {}
