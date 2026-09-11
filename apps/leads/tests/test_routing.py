"""Тесты маршрутизации заявок по отделам.

Внутри филиала техника, запчасти, сервис и складское оборудование — разные люди.
Заявка, ушедшая не туда, теряется, поэтому правила проверяются подробно.
"""

import pytest
from django.test import override_settings

from apps.catalog.factories import MachineTypeFactory
from apps.company.factories import DepartmentFactory
from apps.leads.factories import LeadFactory, LeadRoutingRuleFactory
from apps.leads.models import Lead
from apps.leads.services.routing import match_rule, resolve_recipients

pytestmark = pytest.mark.django_db


def test_rule_matched_by_lead_type(department):
    rule = LeadRoutingRuleFactory(lead_type=Lead.Type.PARTS, department=department)
    LeadRoutingRuleFactory(lead_type=Lead.Type.SERVICE)

    lead = LeadFactory(type=Lead.Type.PARTS)
    assert match_rule(lead) == rule


def test_rule_without_type_matches_anything(department):
    rule = LeadRoutingRuleFactory(lead_type="", department=department)
    assert match_rule(LeadFactory(type=Lead.Type.CALLBACK)) == rule


def test_more_specific_rule_wins_at_same_priority(machine, machine_type):
    """Правило по типу техники точнее правила по одному лишь типу заявки."""
    general = DepartmentFactory(code="sales", name="Продажи")
    forklift = DepartmentFactory(code="forklift", name="Складское оборудование")

    LeadRoutingRuleFactory(lead_type=Lead.Type.PRICE, department=general, priority=10)
    specific = LeadRoutingRuleFactory(
        lead_type="", machine_type=machine_type, department=forklift, priority=10
    )

    lead = LeadFactory(type=Lead.Type.PRICE, machine=machine)
    assert match_rule(lead) == specific


def test_priority_beats_specificity(machine, machine_type):
    """Явно выставленный приоритет важнее вычисленной специфичности."""
    urgent = DepartmentFactory(code="urgent", name="Приоритетный отдел")
    other = DepartmentFactory(code="other", name="Обычный отдел")

    top = LeadRoutingRuleFactory(lead_type=Lead.Type.PRICE, department=urgent, priority=1)
    LeadRoutingRuleFactory(machine_type=machine_type, department=other, priority=50)

    assert match_rule(LeadFactory(type=Lead.Type.PRICE, machine=machine)) == top


def test_machine_type_rule_skipped_for_other_machine(machine, department):
    other_type = MachineTypeFactory(slug="kran", name="Кран")
    LeadRoutingRuleFactory(machine_type=other_type, department=department)
    assert match_rule(LeadFactory(type=Lead.Type.PRICE, machine=machine)) is None


def test_machine_type_rule_skipped_when_no_machine(machine_type, department):
    LeadRoutingRuleFactory(machine_type=machine_type, department=department)
    assert match_rule(LeadFactory(type=Lead.Type.PRICE)) is None


def test_category_rule_matches_machine_category(machine, category, department):
    machine.categories.add(category)
    rule = LeadRoutingRuleFactory(category=category, department=department)
    assert match_rule(LeadFactory(type=Lead.Type.PRICE, machine=machine)) == rule


def test_category_rule_skipped_for_other_category(machine, category, department):
    LeadRoutingRuleFactory(category=category, department=department)
    assert match_rule(LeadFactory(type=Lead.Type.PRICE, machine=machine)) is None


def test_inactive_rule_ignored(department):
    LeadRoutingRuleFactory(lead_type=Lead.Type.PRICE, department=department, is_active=False)
    assert match_rule(LeadFactory(type=Lead.Type.PRICE)) is None


def test_recipients_taken_from_rule(department):
    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE,
        department=department,
        emails=["sales@modernmachinery.ru", "head@modernmachinery.ru"],
    )
    rule, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert rule is not None
    assert recipients == ["sales@modernmachinery.ru", "head@modernmachinery.ru"]


@override_settings(LEADS_FALLBACK_EMAIL="office@modernmachinery.ru")
def test_fallback_used_when_no_rule_matches():
    """Заявка, которая никуда не ушла, — худший из возможных исходов."""
    rule, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert rule is None
    assert recipients == ["office@modernmachinery.ru"]


@override_settings(LEADS_FALLBACK_EMAIL="office@modernmachinery.ru")
def test_fallback_used_when_rule_has_no_emails(department):
    LeadRoutingRuleFactory(lead_type=Lead.Type.PRICE, department=department, emails=[])
    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))
    assert recipients == ["office@modernmachinery.ru"]
