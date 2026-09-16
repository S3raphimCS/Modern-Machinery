"""Шаблонные теги раздела финансирования."""

from django import template
from django.core.cache import cache

from apps.financing.models import TERMS_CACHE_KEY, LeasingTerms
from apps.financing.services.leasing import calculate_leasing

register = template.Library()

CACHE_SECONDS = 600


def get_terms() -> LeasingTerms:
    """Условия финансирования из кэша.

    Плитка каталога выводит платёж на каждой карточке, а условия — синглтон:
    без кэша это был бы запрос к базе на каждую карточку в списке.
    """
    terms = cache.get(TERMS_CACHE_KEY)
    if terms is None:
        terms = LeasingTerms.load()
        cache.set(TERMS_CACHE_KEY, terms, CACHE_SECONDS)
    return terms


@register.simple_tag(takes_context=True)
def leasing_monthly(context, price) -> int | None:
    """Ежемесячный платёж для цены техники, округлённый до рублей.

    Возвращает None, если цена не задана: у большинства позиций она «по
    запросу», и показывать там платёж не от чего.
    """
    if not price:
        return None

    # Условия кладутся в контекст запроса: плитка каталога зовёт тег на каждой
    # карточке, и без этого получалось обращение к кэшу на каждую из них —
    # а при выключенном кэше и вовсе запрос к базе.
    terms = context.get("leasing_terms")
    if terms is None:
        terms = get_terms()
        context.dicts[0]["leasing_terms"] = terms
    result = calculate_leasing(
        price=price,
        advance_percent=terms.min_advance_percent,
        months=terms.default_months,
        markup_percent=terms.default_markup_percent,
    )
    return int(result.monthly_payment)
