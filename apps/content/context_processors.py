"""Контекст, доступный всем шаблонам сайта."""

from django.core.cache import cache

MENU_CACHE_KEY = "content:menu:v1"
SETTINGS_CACHE_KEY = "content:settings:v1"
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
        "site_settings": settings_obj,
        "site_menu": menu,
        "main_branch": Branch.objects.filter(is_published=True).first(),
        "callback_form": CallbackForm(),
    }
