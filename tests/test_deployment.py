"""Проверки, важные при развёртывании.

Эти вещи ломаются молча: сайт отвечает, тесты зелёные, а на свежем сервере
контейнер уходит в unhealthy или браузер попадает в петлю переадресаций.
"""

import pytest
from django.test import override_settings
from django.urls import reverse


@pytest.mark.django_db
@override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^healthz/$"])
def test_healthcheck_is_not_redirected_to_https(client):
    """Проверка живости приходит по http и не должна уходить на https.

    Пока сертификат не выпущен, https не отвечает. Без исключения healthcheck
    контейнера получает 301, идёт по нему в никуда, и nginx на свежем сервере
    объявляется нерабочим — хотя он работает и обслуживает проверку
    Let's Encrypt.
    """
    response = client.get("/healthz/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.django_db
@override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^healthz/$"])
def test_other_pages_still_redirect_to_https(client, branch):
    """Исключение сделано только для проверки живости, а не для всего сайта."""
    response = client.get(reverse("catalog:machine-list"))

    assert response.status_code == 301
    assert response["Location"].startswith("https://")


def test_production_settings_exempt_healthcheck():
    """Исключение задано именно в production-настройках."""
    from config.settings import production

    assert r"^healthz/$" in production.SECURE_REDIRECT_EXEMPT
