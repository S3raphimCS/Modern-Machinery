"""Общие middleware проекта."""

import secrets


class ContentSecurityPolicyMiddleware:
    """Выставляет заголовок Content-Security-Policy.

    Политика строгая по скриптам и мягкая по стилям. Причина в вёрстке: макет
    перенесён с инлайновыми стилями, и запрет `style-src 'unsafe-inline'`
    сломал бы страницы. Риск при этом несопоставим — внедрение стиля не
    выполняет код, а внедрение скрипта выполняет.

    Инлайновые скрипты (микроразметка schema.org) разрешаются по одноразовому
    номеру: он генерируется на каждый запрос и подставляется в шаблон.
    Разрешать их через `'unsafe-inline'` означало бы обессмыслить всю политику.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)

        # Админка и интерактивная документация API рисуются сторонним кодом со
        # своими инлайновыми обработчиками. Ужесточать политику там — ломать
        # рабочие инструменты ради страниц, закрытых от посторонних.
        if request.path.startswith(("/admin/", "/api/docs/", "/api/schema/")):
            return response

        response.setdefault("Content-Security-Policy", self._policy(request.csp_nonce))
        return response

    @staticmethod
    def _policy(nonce: str) -> str:
        directives = {
            "default-src": ["'self'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
            # Кликджекинг закрыт и здесь, и заголовком X-Frame-Options.
            "frame-ancestors": ["'none'"],
            "object-src": ["'none'"],
            "script-src": [
                "'self'",
                f"'nonce-{nonce}'",
                # Счётчик Яндекс.Метрики переносится со старого сайта.
                "https://mc.yandex.ru",
                "https://yandex.ru",
            ],
            "style-src": ["'self'", "'unsafe-inline'"],
            "img-src": ["'self'", "data:", "https://mc.yandex.ru", "https://*.yandex.net"],
            "font-src": ["'self'"],
            "connect-src": ["'self'", "https://mc.yandex.ru"],
            # Карта филиала — виджет Яндекс.Карт.
            "frame-src": ["https://yandex.ru", "https://*.yandex.ru"],
            "upgrade-insecure-requests": [],
        }
        return "; ".join(
            name if not values else f"{name} {' '.join(values)}"
            for name, values in directives.items()
        )
