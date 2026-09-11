"""Дросселирование создания заявок.

Ручка создания заявки — единственная публичная точка записи в базу, поэтому она
защищена в несколько слоёв, а не одним лимитом:

1. `LeadRateThrottle` — длинное окно (по умолчанию 20 заявок в час с одного IP).
   Отсекает планомерный налив базы.
2. `LeadBurstRateThrottle` — короткое окно (3 в минуту). Отсекает всплеск, когда
   скрипт отправляет сотню запросов за секунды и укладывается в часовой лимит.
3. Honeypot и минимальное время заполнения формы — в `apps.leads.forms`.
4. Дедупликация одинаковых заявок — в `apps.leads.services.antispam`.

Обе корзины считаются по IP даже для аутентифицированного пользователя: заявка
публичная, и злоупотребление приходит именно с адреса, а не из-под учётки.
Классы используются и в DRF-представлении, и в обычной HTML-форме, чтобы лимит
нельзя было обойти сменой точки входа.
"""

from apps.core.throttling import SettingsRateThrottle, allows_request


class LeadRateThrottle(SettingsRateThrottle):
    """Длинное окно: защита от планомерного налива заявок."""

    scope = "leads"
    rate_setting = "LEAD_THROTTLE_RATE"


class LeadBurstRateThrottle(SettingsRateThrottle):
    """Короткое окно: защита от всплеска запросов."""

    scope = "leads-burst"
    rate_setting = "LEAD_THROTTLE_BURST_RATE"


def check_lead_throttles(request) -> bool:
    """Проверяет обе корзины для HTML-формы.

    Корзины те же, что и в API, поэтому счётчик общий: тысяча запросов через
    форму не пройдёт мимо лимита только потому, что это не JSON.
    """
    return allows_request(request, LeadBurstRateThrottle, LeadRateThrottle)
