"""Тесты заголовка Content-Security-Policy."""

import re

import pytest

pytestmark = pytest.mark.django_db


def policy(response) -> str:
    return response.headers.get("Content-Security-Policy", "")


def test_policy_present_on_public_pages(client, branch):
    assert "default-src 'self'" in policy(client.get("/"))


def test_scripts_restricted_to_own_origin_and_nonce(client, branch):
    """Разрешать инлайновые скрипты через unsafe-inline — обессмыслить политику."""
    directive = next(
        part for part in policy(client.get("/")).split("; ") if part.startswith("script-src")
    )

    assert "'self'" in directive
    assert "'nonce-" in directive
    assert "'unsafe-inline'" not in directive


def test_styles_allow_inline(client, branch):
    """Макет перенесён с инлайновыми стилями: запрет сломал бы вёрстку.

    Риск несопоставим со скриптами — внедрение стиля не выполняет код.
    """
    assert "style-src 'self' 'unsafe-inline'" in policy(client.get("/"))


def test_framing_and_objects_forbidden(client, branch):
    header = policy(client.get("/"))

    assert "frame-ancestors 'none'" in header
    assert "object-src 'none'" in header


def test_yandex_map_allowed_in_frames(client, branch):
    """Карта проезда — виджет Яндекс.Карт, без разрешения она не отрисуется."""
    assert "frame-src https://yandex.ru" in policy(client.get("/"))


def test_nonce_is_unique_per_request(client, branch):
    pattern = re.compile(r"'nonce-([A-Za-z0-9_-]+)'")
    first = pattern.search(policy(client.get("/"))).group(1)
    second = pattern.search(policy(client.get("/"))).group(1)

    assert first != second


def test_nonce_matches_inline_markup(client, machine):
    """Одноразовый номер в заголовке и в теге должны совпадать.

    Иначе микроразметка не выполнится и schema.org просто исчезнет.
    """
    response = client.get("/")
    header_nonce = re.search(r"'nonce-([A-Za-z0-9_-]+)'", policy(response)).group(1)
    markup_nonce = re.search(
        r'<script type="application/ld\+json" nonce="([A-Za-z0-9_-]+)"',
        response.content.decode(),
    ).group(1)

    assert header_nonce == markup_nonce


@pytest.mark.parametrize("path", ["/admin/login/", "/api/docs/"])
def test_policy_skipped_for_tooling(client, path):
    """Админка и документация API рисуются сторонним кодом со своими скриптами.

    Ужесточать политику там — ломать рабочие инструменты ради страниц,
    закрытых от посторонних.
    """
    assert policy(client.get(path)) == ""
