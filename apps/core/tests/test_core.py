"""Тесты общих утилит и служебных представлений."""

import pytest

from apps.core.utils import get_client_ip, normalize_article, slugify_ru, transliterate


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Экскаватор", "Ekskavator"),
        ("Хабаровск", "Habarovsk"),
        ("Komatsu PC400", "Komatsu PC400"),
        ("Щётка", "Schetka"),
    ],
)
def test_transliterate(raw, expected):
    assert transliterate(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Гидравлический экскаватор", "gidravlicheskiy-ekskavator"),
        ("Komatsu PC400-8", "komatsu-pc400-8"),
        ("  Много   пробелов  ", "mnogo-probelov"),
        ("Спец!символы@убраны", "spetssimvolyubrany"),
    ],
)
def test_slugify_ru(raw, expected):
    assert slugify_ru(raw) == expected


def test_slugify_respects_max_length():
    assert len(slugify_ru("а" * 300, max_length=50)) <= 50


def test_normalize_article_strips_separators():
    assert normalize_article("600-311 3750") == "6003113750"


def test_client_ip_from_remote_addr(rf):
    request = rf.get("/")
    request.META["REMOTE_ADDR"] = "203.0.113.1"
    assert get_client_ip(request) == "203.0.113.1"


def test_client_ip_prefers_forwarded_header(rf):
    """За nginx настоящий адрес клиента приходит в заголовке."""
    request = rf.get("/")
    request.META["REMOTE_ADDR"] = "10.0.0.1"
    request.META["HTTP_X_FORWARDED_FOR"] = "198.51.100.5, 10.0.0.1"
    assert get_client_ip(request) == "198.51.100.5"


@pytest.mark.django_db
def test_healthcheck_reports_database(client):
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}
