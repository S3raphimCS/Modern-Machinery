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
from apps.leads.models import Lead
from apps.leads.services.routing import resolve_recipients
from apps.users.factories import UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_flagged_user_receives_leads(department):
    """Сотрудник с галочкой попадает в получатели без правки правил."""
    UserFactory(email="rukovoditel@modernmachinery.ru", receives_lead_emails=True)
    LeadRoutingRuleFactory(lead_type=Lead.Type.PRICE, department=department, emails=[])

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert recipients == ["rukovoditel@modernmachinery.ru"]


def test_department_mailbox_and_subscriber_combined(department):
    """Общий ящик отдела и личная подписка складываются, а не заменяют друг друга."""
    UserFactory(email="rukovoditel@modernmachinery.ru", receives_lead_emails=True)
    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE, department=department, emails=["parts@modernmachinery.ru"]
    )

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    # Ящик отдела первым: он основной адресат, подписка — дополнение.
    assert recipients == ["parts@modernmachinery.ru", "rukovoditel@modernmachinery.ru"]


def test_same_address_is_not_duplicated(department):
    """Человек может быть и в списке отдела, и подписан лично."""
    UserFactory(email="sales@modernmachinery.ru", receives_lead_emails=True)
    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE, department=department, emails=["sales@modernmachinery.ru"]
    )

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert recipients == ["sales@modernmachinery.ru"]


def test_subscriber_without_department_gets_everything(department):
    """Руководитель без отдела видит поток целиком."""
    UserFactory(email="boss@modernmachinery.ru", receives_lead_emails=True, department=None)
    LeadRoutingRuleFactory(lead_type=Lead.Type.PARTS, department=department, emails=[])

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PARTS))

    assert "boss@modernmachinery.ru" in recipients


def test_subscriber_gets_only_own_department():
    """Менеджер по запчастям не тонет в заявках на технику."""
    parts = DepartmentFactory(code="parts", name="Запчасти")
    sales = DepartmentFactory(code="sales", name="Продажи техники")
    UserFactory(email="parts@modernmachinery.ru", receives_lead_emails=True, department=parts)

    LeadRoutingRuleFactory(lead_type=Lead.Type.PRICE, department=sales, emails=[])
    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert "parts@modernmachinery.ru" not in recipients


def test_subscriber_gets_own_department_leads():
    parts = DepartmentFactory(code="parts", name="Запчасти")
    UserFactory(email="parts@modernmachinery.ru", receives_lead_emails=True, department=parts)
    LeadRoutingRuleFactory(lead_type=Lead.Type.PARTS, department=parts, emails=[])

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PARTS))

    assert recipients == ["parts@modernmachinery.ru"]


def test_unflagged_user_is_ignored(department):
    UserFactory(email="molchun@modernmachinery.ru", receives_lead_emails=False)
    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PRICE, department=department, emails=["parts@modernmachinery.ru"]
    )

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert "molchun@modernmachinery.ru" not in recipients


def test_inactive_user_is_ignored(department):
    """Уволенный сотрудник перестаёт получать заявки вместе с доступом."""
    UserFactory(email="uvolen@modernmachinery.ru", receives_lead_emails=True, is_active=False)
    LeadRoutingRuleFactory(lead_type=Lead.Type.PRICE, department=department, emails=[])

    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert "uvolen@modernmachinery.ru" not in recipients


@override_settings(LEADS_FALLBACK_EMAIL="office@modernmachinery.ru")
def test_fallback_when_nobody_subscribed():
    """Заявка, которая никуда не ушла, — худший из возможных исходов."""
    _, recipients = resolve_recipients(LeadFactory(type=Lead.Type.PRICE))

    assert recipients == ["office@modernmachinery.ru"]


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

    UserFactory(email="rukovoditel@modernmachinery.ru", receives_lead_emails=True)
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
    assert mail.outbox[0].to == ["rukovoditel@modernmachinery.ru"]
    assert "Иванов" in mail.outbox[0].body


def test_routing_report_lists_recipients(department):
    """Команда показывает получателей, не отправляя заявку с сайта."""
    from io import StringIO

    from django.core.management import call_command

    UserFactory(email="rukovoditel@modernmachinery.ru", receives_lead_emails=True)
    LeadRoutingRuleFactory(
        name="Запрос цены", lead_type=Lead.Type.PRICE, department=department, emails=[]
    )

    out = StringIO()
    call_command("check_lead_routing", lead_type=Lead.Type.PRICE, stdout=out)
    report = out.getvalue()

    assert "Запрос цены" in report
    assert "rukovoditel@modernmachinery.ru" in report


def test_routing_report_warns_when_no_rule(db):
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("check_lead_routing", lead_type=Lead.Type.CALLBACK, stdout=out)

    assert "не найдено" in out.getvalue()
