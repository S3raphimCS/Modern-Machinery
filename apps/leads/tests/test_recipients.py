"""Тесты подбора получателей письма о заявке.

Получатели складываются из двух источников: общих ящиков отдела в правиле
маршрутизации и сотрудников, подписавшихся галочкой в своей учётной записи.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import override_settings

from apps.company.factories import DepartmentFactory
from apps.leads.factories import LeadFactory, LeadRoutingRuleFactory
from apps.leads.models import Lead, LeadRoutingRule
from apps.leads.services.routing import resolve_recipients
from apps.users.factories import UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_flagged_user_receives_leads(department):
    """Сотрудник с галочкой попадает в получатели без правки правил."""
    UserFactory(email="rukovoditel@modernmachinery.example", receives_lead_emails=True)
    LeadRoutingRuleFactory(lead_type=Lead.Type.PRICE, department=department, emails=[])

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert recipients == ["rukovoditel@modernmachinery.example"]


def test_department_mailbox_and_subscriber_combined(department):
    """Общий ящик отдела и личная подписка складываются, а не заменяют друг друга."""
    UserFactory(email="rukovoditel@modernmachinery.example", receives_lead_emails=True)
    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE, department=department, emails=["parts@modernmachinery.example"]
    )

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    # Ящик отдела первым: он основной адресат, подписка — дополнение.
    assert recipients == ["parts@modernmachinery.example", "rukovoditel@modernmachinery.example"]


def test_same_address_is_not_duplicated(department):
    """Человек может быть и в списке отдела, и подписан лично."""
    UserFactory(email="sales@modernmachinery.example", receives_lead_emails=True)
    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE, department=department, emails=["sales@modernmachinery.example"]
    )

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert recipients == ["sales@modernmachinery.example"]


def test_subscriber_without_department_gets_everything(department):
    """Руководитель без отдела видит поток целиком."""
    UserFactory(email="boss@modernmachinery.example", receives_lead_emails=True, department=None)
    LeadRoutingRuleFactory(lead_type=Lead.Type.PARTS, department=department, emails=[])

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PARTS))

    assert "boss@modernmachinery.example" in recipients


def test_subscriber_gets_only_own_department():
    """Менеджер по запчастям не тонет в заявках на технику."""
    parts = DepartmentFactory(code="parts", name="Запчасти")
    sales = DepartmentFactory(code="sales", name="Продажи техники")
    UserFactory(email="parts@modernmachinery.example", receives_lead_emails=True, department=parts)

    LeadRoutingRuleFactory(lead_type=Lead.Type.PRICE, department=sales, emails=[])
    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert "parts@modernmachinery.example" not in recipients


def test_subscriber_gets_own_department_leads():
    parts = DepartmentFactory(code="parts", name="Запчасти")
    UserFactory(email="parts@modernmachinery.example", receives_lead_emails=True, department=parts)
    LeadRoutingRuleFactory(lead_type=Lead.Type.PARTS, department=parts, emails=[])

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PARTS))

    assert recipients == ["parts@modernmachinery.example"]


def test_unflagged_user_is_ignored(department):
    UserFactory(email="molchun@modernmachinery.example", receives_lead_emails=False)
    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE, department=department, emails=["parts@modernmachinery.example"]
    )

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert "molchun@modernmachinery.example" not in recipients


def test_inactive_user_is_ignored(department):
    """Уволенный сотрудник перестаёт получать заявки вместе с доступом."""
    UserFactory(email="uvolen@modernmachinery.example", receives_lead_emails=True, is_active=False)
    LeadRoutingRuleFactory(lead_type=Lead.Type.PRICE, department=department, emails=[])

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert "uvolen@modernmachinery.example" not in recipients


@override_settings(LEADS_FALLBACK_EMAIL="office@modernmachinery.example")
def test_fallback_when_nobody_subscribed():
    """Заявка, которая никуда не ушла, — худший из возможных исходов."""
    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert recipients == ["office@modernmachinery.example"]


def test_flag_requires_email():
    """Получатель без адреса — это молча потерянные заявки."""
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(username="bezpochty", email="", receives_lead_emails=True)


def test_user_without_email_allowed_when_not_subscribed():
    User.objects.create(username="bezpochty", email="", receives_lead_emails=False)
    assert User.objects.filter(username="bezpochty").exists()


def test_letter_actually_reaches_subscriber(
    consent, department, machine, django_capture_on_commit_callbacks
):
    """Сквозная проверка: заявка с сайта доходит письмом до подписчика."""
    from apps.leads.services.creation import create_lead

    UserFactory(email="rukovoditel@modernmachinery.example", receives_lead_emails=True)
    LeadRoutingRuleFactory(lead_type=Lead.Type.PRICE, department=department, emails=[])

    with django_capture_on_commit_callbacks(execute=True):
        create_lead(
            data={
                "type": Lead.Type.PRICE,
                "name": "Иванов",
                "phone": "+7 914 000-11-22",
                "machine": machine,
            }
        )

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["rukovoditel@modernmachinery.example"]
    assert "Иванов" in mail.outbox[0].body


def test_routing_report_lists_recipients(department):
    """Команда показывает получателей, не отправляя заявку с сайта."""
    from io import StringIO

    from django.core.management import call_command

    UserFactory(email="rukovoditel@modernmachinery.example", receives_lead_emails=True)
    LeadRoutingRuleFactory(
        name="Запрос цены", lead_type=Lead.Type.PRICE, department=department, emails=[]
    )

    out = StringIO()
    call_command("check_lead_routing", lead_type=Lead.Type.PRICE, stdout=out)
    report = out.getvalue()

    assert "Запрос цены" in report
    assert "rukovoditel@modernmachinery.example" in report


def test_routing_report_warns_when_no_rule(db):
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("check_lead_routing", lead_type=Lead.Type.CALLBACK, stdout=out)

    assert "не найдено" in out.getvalue()


def call_remove(*addresses, dry_run=False) -> str:
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("remove_lead_email", *addresses, dry_run=dry_run, stdout=out)
    return out.getvalue()


def test_remove_email_drops_address_from_rules(department):
    rule = LeadRoutingRuleFactory(
        name="Запрос цены",
        lead_type=Lead.Type.PRICE,
        department=department,
        emails=["sales@modernmachinery.example", "head@modernmachinery.example"],
    )

    call_remove("sales@modernmachinery.example")

    rule.refresh_from_db()
    assert rule.emails == ["head@modernmachinery.example"]


def test_remove_email_keeps_the_rule_itself(department):
    """Правило остаётся: оно продолжает определять отдел заявки."""
    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE, department=department, emails=["sales@modernmachinery.example"]
    )
    UserFactory(email="rukovoditel@modernmachinery.example", receives_lead_emails=True)

    call_remove("sales@modernmachinery.example")
    rule, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert rule is not None
    assert rule.department == department
    assert recipients == ["rukovoditel@modernmachinery.example"]


def test_remove_email_does_not_touch_other_addresses(department):
    other = LeadRoutingRuleFactory(
        name="Запчасти",
        lead_type=Lead.Type.PARTS,
        department=department,
        emails=["parts@modernmachinery.example"],
    )

    call_remove("sales@modernmachinery.example")

    other.refresh_from_db()
    assert other.emails == ["parts@modernmachinery.example"]


def test_remove_email_is_case_insensitive(department):
    rule = LeadRoutingRuleFactory(department=department, emails=["Sales@ModernMachinery.example"])

    call_remove("sales@modernmachinery.example")

    rule.refresh_from_db()
    assert rule.emails == []


def test_remove_email_dry_run_changes_nothing(department):
    rule = LeadRoutingRuleFactory(department=department, emails=["sales@modernmachinery.example"])

    report = call_remove("sales@modernmachinery.example", dry_run=True)

    rule.refresh_from_db()
    assert rule.emails == ["sales@modernmachinery.example"]
    assert "не сохранено" in report


def test_remove_email_reports_when_nothing_matches(department):
    LeadRoutingRuleFactory(department=department, emails=["parts@modernmachinery.example"])

    assert "нет" in call_remove("sales@modernmachinery.example")


@pytest.mark.parametrize("run_twice", [True])
def test_seed_does_not_restore_removed_addresses(run_twice):
    """Повторное наполнение не возвращает демонстрационные адреса.

    Список получателей менеджер правит под реальные ящики филиала. Если
    seed_demo затирал бы его, после каждого обновления данных письма снова
    уходили бы на демонстрационные адреса.
    """
    from django.core.management import call_command

    call_command("seed_demo", "--parts", 5, "--quiet", "--no-images")
    rule = LeadRoutingRule.objects.get(name="Запрос цены на технику")
    assert rule.emails == ["sales@modernmachinery.example"]

    rule.emails = ["moy@yandex.ru"]
    rule.save(update_fields=["emails"])

    call_command("seed_demo", "--parts", 5, "--quiet", "--no-images")

    rule.refresh_from_db()
    assert rule.emails == ["moy@yandex.ru"]


def test_seed_still_updates_other_rule_fields():
    """Всё, кроме адресов, повторное наполнение по-прежнему приводит в порядок."""
    from django.core.management import call_command

    call_command("seed_demo", "--parts", 5, "--quiet", "--no-images")
    rule = LeadRoutingRule.objects.get(name="Запрос цены на технику")
    rule.is_active = False
    rule.priority = 999
    rule.save(update_fields=["is_active", "priority"])

    call_command("seed_demo", "--parts", 5, "--quiet", "--no-images")

    rule.refresh_from_db()
    assert rule.is_active is True
    assert rule.priority == 50


def test_remove_by_domain_clears_every_address(department):
    """Одной командой убирается весь домен, а не адреса по одному."""
    from io import StringIO

    from django.core.management import call_command

    first = LeadRoutingRuleFactory(
        name="Цена", department=department, emails=["sales@modernmachinery.example"]
    )
    second = LeadRoutingRuleFactory(
        name="Запчасти",
        department=department,
        emails=["parts@modernmachinery.example", "moy@yandex.ru"],
    )

    out = StringIO()
    call_command("remove_lead_email", domains=["modernmachinery.example"], stdout=out)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.emails == []
    assert second.emails == ["moy@yandex.ru"]


def test_remove_by_domain_covers_subdomains(department):
    from io import StringIO

    from django.core.management import call_command

    rule = LeadRoutingRuleFactory(
        department=department, emails=["khv@filial.modernmachinery.example"]
    )

    call_command("remove_lead_email", domains=["modernmachinery.example"], stdout=StringIO())

    rule.refresh_from_db()
    assert rule.emails == []


def test_remove_requires_an_argument():
    from io import StringIO

    from django.core.management import call_command
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="Укажите адрес"):
        call_command("remove_lead_email", stdout=StringIO())


@override_settings(LEADS_BLOCKED_EMAIL_DOMAINS=["modernmachinery.ru"])
def test_blocked_domain_never_receives_mail(department):
    """Предохранитель: адрес настоящей компании не получит заявку.

    Даже если он остался в правиле или его вписали в админке.
    """
    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE, department=department, emails=["sales@modernmachinery.ru"]
    )
    UserFactory(email="moy@yandex.ru", receives_lead_emails=True)

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert recipients == ["moy@yandex.ru"]


@override_settings(LEADS_BLOCKED_EMAIL_DOMAINS=["modernmachinery.ru"])
def test_blocked_domain_covers_subdomains(department):
    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE,
        department=department,
        emails=["khv@filial.modernmachinery.ru"],
    )

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert recipients == []


@override_settings(
    LEADS_BLOCKED_EMAIL_DOMAINS=["modernmachinery.ru"],
    LEADS_FALLBACK_EMAIL="office@modernmachinery.ru",
)
def test_blocked_fallback_is_not_used(department):
    """Резервный адрес проверяется так же: он тоже может быть чужим."""
    LeadRoutingRuleFactory(lead_type=Lead.Type.PRICE, department=department, emails=[])

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert recipients == []


@override_settings(LEADS_BLOCKED_EMAIL_DOMAINS=[])
def test_nothing_blocked_by_default(department):
    """На рабочем сайте компании список пуст — её собственная почта работает."""
    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE, department=department, emails=["sales@modernmachinery.ru"]
    )

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert recipients == ["sales@modernmachinery.ru"]


@override_settings(
    LEADS_BLOCKED_EMAIL_DOMAINS=["modernmachinery.ru"],
    LEADS_FALLBACK_EMAIL="office@modernmachinery.ru",
)
def test_no_letter_sent_when_everyone_blocked(machine, django_capture_on_commit_callbacks):
    """Письмо не уходит вовсе, а в истории заявки остаётся след."""
    from apps.leads.models import LeadEvent
    from apps.leads.tasks import send_lead_notification

    lead = LeadFactory(machine=machine)
    result = send_lead_notification(lead.pk, [])

    assert result == "no-recipients"
    assert mail.outbox == []
    assert lead.events.filter(kind=LeadEvent.Kind.EMAIL_FAILED).exists()
