"""Дросселирование поиска по каталогу.

Автодополнение стреляет запросом на каждое нажатие клавиши, а за ним стоит
полнотекстовый поиск с ранжированием — самая дорогая операция каталога.
Без лимита это дешёвый способ уронить базу, поэтому ручка защищена так же,
как форма заявок.
"""

from apps.core.throttling import SettingsRateThrottle, allows_request


class SearchRateThrottle(SettingsRateThrottle):
    """Ограничение частоты запросов к поиску по одному адресу."""

    scope = "search"
    rate_setting = "SEARCH_THROTTLE_RATE"


def check_search_throttle(request) -> bool:
    return allows_request(request, SearchRateThrottle)
