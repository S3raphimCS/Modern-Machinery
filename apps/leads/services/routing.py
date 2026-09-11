"""Маршрутизация заявки: в какой отдел и на какие адреса она уходит."""

from __future__ import annotations

from django.conf import settings

from apps.leads.models import Lead, LeadRoutingRule


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


def resolve_recipients(lead: Lead) -> tuple[LeadRoutingRule | None, list[str]]:
    """Определяет правило и список адресов получателей.

    Если ни одно правило не подошло, письмо уходит на резервный адрес: заявка,
    которая никуда не ушла, — худший из возможных исходов.
    """
    rule = match_rule(lead)
    if rule and rule.emails:
        return rule, list(rule.emails)
    return rule, [settings.LEADS_FALLBACK_EMAIL]
