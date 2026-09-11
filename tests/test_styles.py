"""Проверка, что вёрстка не ссылается на несуществующие стили.

Класс без правила в CSS — самый незаметный вид поломки: страница отдаёт 200,
тесты зелёные, а блок выглядит как неоформленная заготовка. Ровно так однажды
и оказался без оформления калькулятор стоимости владения.
"""

import re
from pathlib import Path

from django.conf import settings

CLASS_ATTRIBUTE = re.compile(r'class="([^"]*)"')
CSS_SELECTOR = re.compile(r"\.(mm-[a-z0-9_-]+)")
PREFIX = "mm-"


def collect_defined_classes() -> set[str]:
    css = Path(settings.BASE_DIR) / "static" / "css" / "main.css"
    return set(CSS_SELECTOR.findall(css.read_text(encoding="utf-8")))


def collect_used_classes() -> dict[str, set[str]]:
    """Классы проекта, встречающиеся в шаблонах, вместе с именами файлов."""
    used: dict[str, set[str]] = {}
    for template in (Path(settings.BASE_DIR) / "templates").rglob("*.html"):
        content = template.read_text(encoding="utf-8")
        for attribute in CLASS_ATTRIBUTE.findall(content):
            for name in attribute.split():
                # Значения, собираемые шаблонизатором, проверить статически нельзя.
                if name.startswith(PREFIX) and "{" not in name:
                    used.setdefault(name, set()).add(template.name)
    return used


def test_every_used_class_has_styles():
    defined = collect_defined_classes()
    used = collect_used_classes()

    missing = {name: sorted(files) for name, files in used.items() if name not in defined}
    assert missing == {}, f"Классы без стилей: {missing}"


def test_project_classes_are_actually_used():
    """Обратная проверка: правило, на которое никто не ссылается, — мёртвый код.

    Модификаторы состояния (`is-active`, `--empty`) навешиваются скриптом, а не
    в разметке, поэтому исключены из проверки.
    """
    script_driven = {"mm-htmx-indicator", "mm-compare-bar__text"}
    defined = collect_defined_classes()
    used = set(collect_used_classes())

    unused = sorted(
        name for name in defined - used - script_driven if "--" not in name and "__" not in name
    )
    assert unused == [], f"Стили без разметки: {unused}"


# Теги с голым атрибутом `hidden` (а не `hidden="..."`).
HIDDEN_TAG = re.compile(r"<[a-z][^>]*\shidden(?=[\s>])[^>]*>", re.IGNORECASE)
CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.MULTILINE)


def collect_hidden_classes() -> dict[str, set[str]]:
    """Классы элементов, которые скрываются атрибутом `hidden`."""
    result: dict[str, set[str]] = {}
    for template in (Path(settings.BASE_DIR) / "templates").rglob("*.html"):
        content = template.read_text(encoding="utf-8")
        for tag in HIDDEN_TAG.findall(content):
            match = CLASS_ATTRIBUTE.search(tag)
            if not match:
                continue
            for name in match.group(1).split():
                if name.startswith(PREFIX) and "{" not in name:
                    result.setdefault(name, set()).add(template.name)
    return result


def classes_declaring_display() -> set[str]:
    """Классы, у которых задано собственное свойство display."""
    css = (Path(settings.BASE_DIR) / "static" / "css" / "main.css").read_text(encoding="utf-8")
    declaring = set()
    for selector, body in CSS_RULE.findall(css):
        if not re.search(r"(^|[;\s])display\s*:", body):
            continue
        for part in selector.split(","):
            part = part.strip()
            # Интересуют только правила на сам класс, без вложенности и состояний.
            simple = re.fullmatch(r"\.(mm-[a-z0-9_-]+)", part)
            if simple:
                declaring.add(simple.group(1))
    return declaring


def test_hidden_elements_are_actually_hidden():
    """Атрибут `hidden` должен побеждать собственный display класса.

    Селектор по классу специфичнее браузерного `[hidden] { display: none }`,
    поэтому элемент с `display: flex` остаётся на экране, даже когда скрипт
    выставил ему `hidden`. Ровно так плашка сравнения висела постоянно.
    """
    css = (Path(settings.BASE_DIR) / "static" / "css" / "main.css").read_text(encoding="utf-8")
    declaring = classes_declaring_display()

    broken = {
        name: sorted(files)
        for name, files in collect_hidden_classes().items()
        if name in declaring and f".{name}[hidden]" not in css
    }
    assert broken == {}, (
        "Элементы скрываются атрибутом hidden, но их класс задаёт display "
        f"и не имеет правила [hidden]: {broken}"
    )
