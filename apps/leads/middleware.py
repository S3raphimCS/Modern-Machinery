"""Запоминание источника перехода.

Метки кампании приходят в адресе страницы, на которую человек попал с рекламы.
Форма заявки отправляется отдельным запросом на `/zayavka/<тип>/` — адрес без
параметров, — поэтому к моменту создания заявки меток в запросе уже нет.
Посредник кладёт их в cookie, а `collect_request_meta` читает оттуда.
"""

from __future__ import annotations

from django.core import signing

COOKIE_NAME = "mm_src"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 дней

# Ключи, которые вообще имеет смысл запоминать. Белый список, а не «всё, что
# пришло»: значение доезжает до письма менеджеру и до админки.
TRACKED_KEYS = (
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    # Идентификатор клика Яндекс.Директа: без него заявку не связать с кампанией.
    "yclid",
)

MAX_VALUE_LENGTH = 200
MAX_COOKIE_LENGTH = 1024

# Разделы, где метка бесполезна: админка, машинный интерфейс и раздача файлов.
IGNORED_PREFIXES = ("/admin/", "/api/", "/static/", "/media/")


def read_marks(request) -> dict:
    """Возвращает запомненные метки или пустой словарь.

    Испорченная подпись — не повод отдавать ошибку: заявка важнее аналитики,
    поэтому такая cookie просто считается отсутствующей.
    """
    raw = request.COOKIES.get(COOKIE_NAME)
    if not raw:
        return {}
    try:
        # Срок проверяется и здесь: браузер может вернуть cookie и позже, а
        # подпись сама по себе бессрочна.
        marks = signing.loads(raw, max_age=COOKIE_MAX_AGE)
    except signing.BadSignature:
        return {}
    if not isinstance(marks, dict):
        return {}
    return {key: value for key, value in marks.items() if key in TRACKED_KEYS}


def _collect(request) -> dict:
    """Забирает известные метки из адреса запроса."""
    marks = {}
    for key in TRACKED_KEYS:
        value = request.GET.get(key, "").strip()
        if value:
            marks[key] = value[:MAX_VALUE_LENGTH]
    return marks


class SourceTrackingMiddleware:
    """Пишет метки кампании в подписанную cookie.

    Стоит ниже `CommonMiddleware`, поэтому переадресация со слешем на конце
    возвращается, не дойдя сюда. Метка при этом не теряется: Django сохраняет
    строку параметров, и её запишет следующий запрос — цена вопроса один
    лишний переход.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.method != "GET":
            return response
        if request.path.startswith(IGNORED_PREFIXES):
            return response
        if not response.get("Content-Type", "").startswith("text/html"):
            return response

        marks = _collect(request)
        # Переход внутри сайта метку не затирает: без параметров в адресе
        # запомненный источник остаётся прежним.
        if not marks:
            return response

        value = signing.dumps(marks)
        if len(value) > MAX_COOKIE_LENGTH:
            return response

        response.set_cookie(
            COOKIE_NAME,
            value,
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure(),
        )
        # Кеширования HTML в проекте нет ни в Django, ни в nginx, поэтому
        # `Vary: Cookie` сейчас не нужен. Если кеш появится, его придётся
        # добавить здесь: иначе страница с чужой меткой уедет другому человеку.
        return response
