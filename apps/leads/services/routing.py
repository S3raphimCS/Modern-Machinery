"""Маршрутизация заявки: в какой отдел и на какие адреса она уходит."""

from __future__ import annotations

import logging

from django.conf import settings

from apps.leads.models import Lead, LeadRoutingRule

logger = logging.getLogger(__name__)


def match_rule(lead: Lead) -> LeadRoutingRule | None:
    """Находит первое подходящее правило маршрутизации.

    Правила проверяются по возрастанию приоритета, а среди равных выигрывает
    более специфичное: правило с указанным типом техники точнее правила,
    заданного только типом заявки.
    """
    rules = LeadRoutingRule.objects.filter(is_active=True).select_related("department")
    machine = lead.machine
    candidates = []

    for rule in rules:
        if rule.lead_type and rule.lead_type != lead.type:
            continue
        specificity = 0
        if rule.machine_type_id:
            if machine is None or machine.machine_type_id != rule.machine_type_id:
                continue
            specificity += 2
        if rule.category_id:
            if machine is None or not machine.categories.filter(pk=rule.category_id).exists():
                continue
            specificity += 2
        if rule.lead_type:
            specificity += 1
        candidates.append((rule.priority, -specificity, rule.pk, rule))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[:3])
    return candidates[0][3]


def is_blocked(address: str) -> bool:
    """Запрещена ли отправка на этот адрес.

    Сравнивается домен целиком и его поддомены: `modernmachinery.ru` в списке
    закрывает и `khv.modernmachinery.ru`.
    """
    blocked = getattr(settings, "LEADS_BLOCKED_EMAIL_DOMAINS", [])
    if not blocked or "@" not in address:
        return False

    domain = address.rsplit("@", 1)[1].strip().lower()
    return any(domain == item or domain.endswith(f".{item}") for item in blocked)


def filter_blocked(addresses: list[str]) -> list[str]:
    """Убирает из списка адреса на запрещённых доменах."""
    allowed = []
    for address in addresses:
        if is_blocked(address):
            logger.warning("Отправка на %s запрещена настройкой домена", address)
            continue
        allowed.append(address)
    return allowed


def resolve_recipients(lead: Lead) -> tuple[LeadRoutingRule | None, list[str]]:
    """Определяет правило и список адресов получателей.

    Адреса берутся из двух источников и объединяются:

    1. Правило маршрутизации — общие ящики отделов вроде `parts@`. Их держит
       и меняет менеджер, не трогая учётные записи.
    2. Сотрудники с включённой галочкой «Получать заявки на почту». Так
       руководитель подписывается на поток сам, без правки правил.

    Если не нашлось ни того, ни другого, письмо уходит на резервный адрес:
    заявка, которая никуда не ушла, — худший из возможных исходов.
    """
    from django.contrib.auth import get_user_model

    rule = match_rule(lead)
    department = rule.department if rule else None

    recipients: list[str] = list(rule.emails) if rule and rule.emails else []
    recipients += (
        get_user_model().objects.lead_recipients(department).values_list("email", flat=True)
    )

    # Один человек может быть и в списке отдела, и подписан лично: письмо
    # должно прийти один раз. Порядок сохраняем — первым идёт ящик отдела.
    unique = list(dict.fromkeys(address for address in recipients if address))

    allowed = filter_blocked(unique)
    if allowed:
        return rule, allowed

    # Сюда попадаем, если получателей не нашлось вовсе либо все они оказались
    # на запрещённом домене. Резервный адрес проверяется так же: он тоже может
    # указывать на чужую почту.
    return rule, filter_blocked([settings.LEADS_FALLBACK_EMAIL])
