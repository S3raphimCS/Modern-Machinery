"""Мелкие утилиты, нужные более чем одному приложению."""

import re
import unicodedata

# Транслитерация по ГОСТ-подобной схеме: нужна, чтобы slug из русского названия
# получался читаемым латиницей, а не пустой строкой.
_TRANSLIT_MAP = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def transliterate(value: str) -> str:
    """Переводит кириллицу в латиницу, оставляя остальные символы как есть."""
    result = []
    for char in value:
        lower = char.lower()
        if lower in _TRANSLIT_MAP:
            replacement = _TRANSLIT_MAP[lower]
            # Заглавная «Щ» превращается в «Sch», а не в «SCH»: замена из
            # нескольких букв должна получить только заглавную первую.
            result.append(replacement.capitalize() if char.isupper() else replacement)
        else:
            result.append(char)
    return "".join(result)


def slugify_ru(value: str, max_length: int = 180) -> str:
    """Строит ЧПУ-совместимый slug из строки на русском или латинице."""
    value = transliterate(str(value))
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[-\s]+", "-", value)
    return value[:max_length].strip("-")


def normalize_article(value: str) -> str:
    """Приводит артикул к канонической форме для поиска.

    Снабженец вводит `600 311 3750`, `600-311-3750` или `6003113750` — во всех трёх
    случаях должна находиться одна и та же позиция.
    """
    return re.sub(r"[^0-9A-Za-zА-Яа-я]", "", str(value)).upper()


def get_client_ip(request) -> str | None:
    """Достаёт IP клиента с учётом того, что приложение стоит за nginx."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        # Первый адрес в цепочке — исходный клиент, остальные добавили прокси.
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
