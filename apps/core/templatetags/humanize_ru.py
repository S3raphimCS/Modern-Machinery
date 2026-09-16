"""Фильтры для русского текста в шаблонах."""

from django import template

register = template.Library()


@register.filter
def plural_ru(count, forms: str) -> str:
    """Выбирает форму слова по числу: «1 оценка», «2 оценки», «17 оценок».

    Встроенный `pluralize` рассчитан на английский и понимает только две
    формы; с тремя через запятую он молча возвращает пустую строку, и слово
    со страницы просто исчезает.

    Формы перечисляются через запятую в порядке «1, 2, 5».
    """
    variants = [form.strip() for form in forms.split(",")]
    if len(variants) != 3:
        raise template.TemplateSyntaxError(
            "plural_ru ожидает три формы через запятую, например «оценка,оценки,оценок»"
        )

    try:
        number = abs(int(count))
    except (TypeError, ValueError):
        return variants[2]

    # 11–14 выбиваются из общего правила: «11 оценок», а не «11 оценка».
    if number % 100 in range(11, 15):
        return variants[2]
    remainder = number % 10
    if remainder == 1:
        return variants[0]
    if remainder in (2, 3, 4):
        return variants[1]
    return variants[2]
