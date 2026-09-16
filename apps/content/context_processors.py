"""Контекст, доступный всем шаблонам сайта."""

from django.conf import settings
from django.core.cache import cache

from apps.content.models import SETTINGS_CACHE_KEY

MENU_CACHE_KEY = "content:menu:v1"
CACHE_SECONDS = 600


def site_context(request) -> dict:
    """Настройки сайта, меню и филиал — то, что нужно шапке и подвалу на каждой странице."""
    from apps.company.models import Branch

    from .models import MenuItem, SiteSettings

    settings_obj = cache.get(SETTINGS_CACHE_KEY)
    if settings_obj is None:
        settings_obj = SiteSettings.load()
        cache.set(SETTINGS_CACHE_KEY, settings_obj, CACHE_SECONDS)

    menu = cache.get(MENU_CACHE_KEY)
    if menu is None:
        items = MenuItem.objects.filter(is_visible=True).order_by("path")
        menu = {}
        for item in items:
            menu.setdefault(item.location, []).append(item)
        cache.set(MENU_CACHE_KEY, menu, CACHE_SECONDS)

    # Форма обратного звонка есть в подвале каждой страницы, поэтому она
    # создаётся здесь: иначе каждая вьюшка обязана была бы её прокидывать.
    from apps.leads.forms import CallbackForm

    return {
        "metrika_id": _metrika_id(request, settings_obj),
        "metrika_webvisor": settings.METRIKA_WEBVISOR,
        "site_settings": settings_obj,
        "site_menu": menu,
        "main_branch": Branch.objects.filter(is_published=True).first(),
        "callback_form": CallbackForm(),
    }


def _metrika_id(request, settings_obj) -> str:
    """Номер счётчика, если его вообще нужно показывать.

    Значение уходит прямо в вызов JS, поэтому пропускается только строка из
    цифр. Сотрудникам счётчик не отдаётся: на демо-стенде половина заходов
    наша, и без отсечки отчёты состояли бы из нас.
    """
    if not settings.METRIKA_ENABLED:
        return ""

    metrika_id = (settings_obj.metrika_id or "").strip()
    # `isdigit()` пропускает арабо-индийские цифры и надстрочные знаки: строка
    # «١٢٣» его проходит, а в JS даёт синтаксическую ошибку — и тогда не
    # грузится ни счётчик, ни цели, на всём сайте.
    if not (metrika_id.isascii() and metrika_id.isdigit()):
        return ""

    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_staff:
        return ""

    return metrika_id
