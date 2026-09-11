"""Общие классы дросселирования.

Ставка читается из настроек Django в момент запроса. DRF по умолчанию
фиксирует её в атрибуте класса при импорте модуля — тогда лимит нельзя было бы
поменять переменной окружения без перезапуска и нельзя было бы проверить в
тесте.
"""

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class SettingsRateThrottle(SimpleRateThrottle):
    """Корзина, ключ которой строится по IP-адресу клиента.

    По адресу, а не по учётной записи: защищаемые ручки публичные, и
    злоупотребление приходит именно с адреса.
    """

    rate_setting = ""

    def get_rate(self):
        return getattr(settings, self.rate_setting, None)

    def get_cache_key(self, request, view=None):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


def allows_request(request, *throttle_classes) -> bool:
    """Проверяет корзины для не-DRF точек входа: обычных вьюшек Django.

    Возвращает False, если хотя бы одна корзина исчерпана.
    """
    return all(throttle_class().allow_request(request, None) for throttle_class in throttle_classes)
