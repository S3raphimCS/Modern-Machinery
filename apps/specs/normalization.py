"""Нормализация характеристик техники.

Главная ценность каталога — фильтры «мощность от и до». Они возможны только если
значение разобрано в число и единицу измерения, а название параметра сведено к
единой записи в справочнике. На старом сайте характеристики лежат строками прямо
в вёрстке (`«Мощность двиг., кВт — 257»`), поэтому разбор нужен до записи в базу.

Модуль намеренно не зависит от Django: это чистые функции, которые легко
покрываются параметризованными тестами и переиспользуются в командах импорта.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Разделители диапазона: дефис, минус, тире, многоточие, «до».
_RANGE_SEPARATORS = r"(?:\.{2,3}|—|–|−|-|\bдо\b)"

# Пробелы, которые встречаются в разрядах числа: обычный, неразрывный, узкий.
_SPACE_CHARS = "    "

# Приведение единиц к каноническому виду: на старом сайте одна и та же единица
# написана десятком способов, а фильтр обязан сравнивать сопоставимые величины.
_UNIT_ALIASES = {
    "квт": "кВт",
    "kw": "кВт",
    "kвт": "кВт",
    "л.с.": "л.с.",
    "лс": "л.с.",
    "hp": "л.с.",
    "кг": "кг",
    "kg": "кг",
    "т": "т",
    "тонн": "т",
    "тонны": "т",
    "мм": "мм",
    "mm": "мм",
    "см": "см",
    "м": "м",
    "m": "м",
    "м3": "м³",
    "м³": "м³",
    "куб.м": "м³",
    "м2": "м²",
    "м²": "м²",
    "л": "л",
    "л/мин": "л/мин",
    "мпа": "МПа",
    "бар": "бар",
    "кн": "кН",
    "об/мин": "об/мин",
    "км/ч": "км/ч",
    "кмч": "км/ч",
    "квт/ч": "кВт·ч",
    "ква": "кВА",
    "kva": "кВА",
    "в": "В",
    "%": "%",
    "шт": "шт",
    "мч": "м/ч",
}

# Значения, которые означают «да» и «нет» для булевых характеристик.
_TRUE_WORDS = {"да", "есть", "yes", "true", "+", "имеется", "присутствует"}
_FALSE_WORDS = {"нет", "no", "false", "-", "отсутствует"}


@dataclass(frozen=True)
class ParsedValue:
    """Результат разбора строкового значения характеристики."""

    raw: str
    value_num: Decimal | None = None
    value_num_max: Decimal | None = None
    value_bool: bool | None = None
    value_str: str = ""
    unit: str = ""

    @property
    def is_range(self) -> bool:
        """Значение — диапазон, например «глубина копания 6,6–7,4 м»."""
        return self.value_num is not None and self.value_num_max is not None

    @property
    def is_numeric(self) -> bool:
        return self.value_num is not None


def normalize_unit(unit: str) -> str:
    """Приводит единицу измерения к каноническому написанию."""
    cleaned = unit.strip().strip(".,;").replace(" ", "").lower()
    if not cleaned:
        return ""
    return _UNIT_ALIASES.get(cleaned, unit.strip())


def normalize_label(label: str) -> str:
    """Приводит название параметра к виду, пригодному для сравнения.

    Убирает регистр, лишние пробелы, знаки препинания и хвост с единицей
    измерения: `«Мощность двиг., кВт»` и `«мощность двигателя»` должны сойтись
    на один и тот же справочный параметр.
    """
    text = unicodedata.normalize("NFKC", str(label)).lower()
    text = text.replace("ё", "е")
    # Отрезаем хвост вида «, кВт» или «(кВт)» — единица хранится в справочнике.
    text = re.sub(r"[,(]\s*[^,()]*\)?\s*$", "", text) if _looks_like_unit_tail(text) else text
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _looks_like_unit_tail(text: str) -> bool:
    """Проверяет, что хвост строки после запятой или скобки — единица измерения."""
    match = re.search(r"[,(]\s*([^,()]*)\)?\s*$", text)
    if not match:
        return False
    tail = match.group(1).strip().rstrip(".")
    return bool(tail) and tail.replace(" ", "").lower() in _UNIT_ALIASES


def _to_decimal(raw: str) -> Decimal | None:
    """Переводит числовой фрагмент в Decimal, понимая запятую и разряды пробелами."""
    cleaned = raw.strip()
    for space in _SPACE_CHARS:
        cleaned = cleaned.replace(space, "")
    cleaned = cleaned.replace(",", ".")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_value(raw: str, *, default_unit: str = "") -> ParsedValue:
    """Разбирает строковое значение характеристики.

    Понимает одиночные числа (`«257 кВт»`), диапазоны (`«6,6–7,4 м»`), разряды,
    записанные пробелами (`«1 250 кг»`), булевы значения (`«есть»`) и произвольный
    текст, который остаётся строкой.
    """
    text = unicodedata.normalize("NFKC", str(raw)).strip()
    if not text:
        return ParsedValue(raw=str(raw))

    lowered = text.lower().rstrip(".")
    if lowered in _TRUE_WORDS:
        return ParsedValue(raw=text, value_bool=True)
    if lowered in _FALSE_WORDS:
        return ParsedValue(raw=text, value_bool=False)

    number = r"[-+]?\d[\d" + _SPACE_CHARS + r"]*(?:[.,]\d+)?"

    range_match = re.match(
        rf"^\s*(?:от\s*)?({number})\s*{_RANGE_SEPARATORS}\s*({number})\s*(.*)$",
        text,
        flags=re.IGNORECASE,
    )
    if range_match:
        low = _to_decimal(range_match.group(1))
        high = _to_decimal(range_match.group(2))
        unit = normalize_unit(range_match.group(3)) or normalize_unit(default_unit)
        if low is not None and high is not None:
            # Значения могут прийти в обратном порядке — приводим к возрастанию,
            # иначе фильтр «от и до» отсечёт корректную позицию.
            if low > high:
                low, high = high, low
            return ParsedValue(raw=text, value_num=low, value_num_max=high, unit=unit)

    single_match = re.match(
        rf"^\s*(?:около|примерно|~|≈|от|до|более|менее)?\s*({number})\s*(.*)$",
        text,
        flags=re.IGNORECASE,
    )
    if single_match:
        value = _to_decimal(single_match.group(1))
        tail = single_match.group(2).strip()
        # Если после числа идёт осмысленный текст, а не единица, значение
        # не числовое: «4 цилиндра рядно» фильтровать бессмысленно.
        unit = normalize_unit(tail)
        if value is not None and (not tail or unit in _UNIT_ALIASES.values() or len(tail) <= 12):
            return ParsedValue(raw=text, value_num=value, unit=unit or normalize_unit(default_unit))

    return ParsedValue(raw=text, value_str=text[:255], unit=normalize_unit(default_unit))


def build_alias_index(spec_keys) -> dict[str, object]:
    """Строит индекс «нормализованное название → справочный параметр».

    На вход принимает любой итерируемый объект с атрибутами `name` и `aliases`,
    поэтому работает и с моделями, и с простыми заглушками в тестах.
    """
    index: dict[str, object] = {}
    for key in spec_keys:
        index.setdefault(normalize_label(key.name), key)
        for alias in getattr(key, "aliases", None) or []:
            index.setdefault(normalize_label(alias), key)
    return index


def match_spec_key(label: str, alias_index: dict[str, object]):
    """Находит справочный параметр по названию из источника данных."""
    return alias_index.get(normalize_label(label))
