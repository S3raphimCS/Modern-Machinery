"""Тесты нормализации характеристик.

Разбор значений — предусловие всех фильтров каталога: если «257 кВт» не станет
числом 257, фильтр «мощность от и до» не построится ни при какой вёрстке.
"""

from decimal import Decimal

import pytest

from apps.specs.normalization import (
    ParsedValue,
    build_alias_index,
    match_spec_key,
    normalize_label,
    normalize_unit,
    parse_value,
)


class FakeKey:
    """Заглушка справочного параметра: модуль намеренно не зависит от Django."""

    def __init__(self, name, aliases=None):
        self.name = name
        self.aliases = aliases or []


@pytest.mark.parametrize(
    ("raw", "expected_num", "expected_max", "expected_unit"),
    [
        ("257 кВт", Decimal("257"), None, "кВт"),
        ("1 250 кг", Decimal("1250"), None, "кг"),
        ("0,93 м³", Decimal("0.93"), None, "м³"),
        ("24 В", Decimal("24"), None, "В"),
        ("~257 кВт", Decimal("257"), None, "кВт"),
        ("38 500", Decimal("38500"), None, ""),
        ("6,6–7,4 м", Decimal("6.6"), Decimal("7.4"), "м"),
        ("6.6 - 7.4 м", Decimal("6.6"), Decimal("7.4"), "м"),
        ("1,5...2,0 м", Decimal("1.5"), Decimal("2.0"), "м"),
        ("от 150 до 300 кВт", Decimal("150"), Decimal("300"), "кВт"),
    ],
)
def test_parse_value_numbers(raw, expected_num, expected_max, expected_unit):
    result = parse_value(raw)
    assert result.value_num == expected_num
    assert result.value_num_max == expected_max
    assert result.unit == expected_unit


def test_parse_value_reverses_inverted_range():
    """Диапазон, записанный от большего к меньшему, приводится к возрастанию.

    Иначе фильтр «от и до» отсёк бы корректную позицию.
    """
    result = parse_value("7,4–6,6 м")
    assert result.value_num == Decimal("6.6")
    assert result.value_num_max == Decimal("7.4")
    assert result.is_range is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("есть", True), ("Нет", False), ("да", True), ("отсутствует", False), ("+", True)],
)
def test_parse_value_booleans(raw, expected):
    assert parse_value(raw).value_bool is expected


@pytest.mark.parametrize("raw", ["PC400-8", "4 цилиндра рядно", "по запросу"])
def test_parse_value_falls_back_to_string(raw):
    result = parse_value(raw)
    assert result.value_str == raw
    assert result.value_num is None


def test_parse_value_empty_string():
    result = parse_value("")
    assert result == ParsedValue(raw="")
    assert result.is_numeric is False


def test_parse_value_uses_default_unit_when_absent():
    assert parse_value("400", default_unit="кг").unit == "кг"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Мощность двиг., кВт", "мощность двиг"),
        ("Объём ковша (м³)", "объем ковша"),
        ("Эксплуатационная масса, кг", "эксплуатационная масса"),
        ("  Глубина   копания  ", "глубина копания"),
        ("МОЩНОСТЬ ДВИГАТЕЛЯ", "мощность двигателя"),
    ],
)
def test_normalize_label(raw, expected):
    assert normalize_label(raw) == expected


def test_normalize_label_keeps_meaningful_tail():
    """Хвост после запятой отрезается только если это единица измерения."""
    assert normalize_label("Ковш, усиленный") == "ковш усиленный"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("квт", "кВт"), ("KW", "кВт"), ("м3", "м³"), ("  кг ", "кг"), ("", ""), ("лс", "л.с.")],
)
def test_normalize_unit(raw, expected):
    assert normalize_unit(raw) == expected


def test_alias_index_matches_synonyms():
    """Именно синонимы делают повторный импорт идемпотентным."""
    key = FakeKey("Мощность двигателя", ["Мощность двиг.", "Мощность"])
    index = build_alias_index([key])

    assert match_spec_key("Мощность двигателя", index) is key
    assert match_spec_key("Мощность двиг., кВт", index) is key
    assert match_spec_key("мощность", index) is key
    assert match_spec_key("Объём ковша", index) is None


def test_alias_index_first_key_wins_on_conflict():
    first = FakeKey("Мощность", [])
    second = FakeKey("Мощность", [])
    index = build_alias_index([first, second])
    assert match_spec_key("Мощность", index) is first
