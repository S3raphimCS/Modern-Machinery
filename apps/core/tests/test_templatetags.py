"""Тесты фильтров для русского текста."""

import pytest
from django import template

from apps.core.templatetags.humanize_ru import plural_ru


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, "оценка"),
        (2, "оценки"),
        (4, "оценки"),
        (5, "оценок"),
        (0, "оценок"),
        # Второй десяток выбивается из правила целиком.
        (11, "оценок"),
        (12, "оценок"),
        (14, "оценок"),
        (17, "оценок"),
        (21, "оценка"),
        (22, "оценки"),
        (101, "оценка"),
        (111, "оценок"),
        (1002, "оценки"),
    ],
)
def test_form_matches_the_number(count, expected):
    assert plural_ru(count, "оценка,оценки,оценок") == expected


def test_negative_number_uses_its_magnitude():
    assert plural_ru(-21, "оценка,оценки,оценок") == "оценка"


def test_non_number_falls_back_to_the_plural_form():
    """Пустое значение не должно ронять страницу."""
    assert plural_ru(None, "оценка,оценки,оценок") == "оценок"


def test_wrong_number_of_forms_is_a_template_error():
    """Ошибку видно сразу, а не в виде пропавшего слова на странице."""
    with pytest.raises(template.TemplateSyntaxError):
        plural_ru(1, "оценка,оценки")
