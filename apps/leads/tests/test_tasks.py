"""Тесты фоновых задач по заявкам."""

import datetime

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.leads.factories import LeadFactory
from apps.leads.models import Lead, LeadEvent
from apps.leads.tasks import purge_expired_leads, send_lead_notification

pytestmark = pytest.mark.django_db


def test_notification_sent_to_recipients(machine):
    lead = LeadFactory(machine=machine)
    result = send_lead_notification(lead.pk, ["parts@modernmachinery.ru"])

    assert result == "sent"
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["parts@modernmachinery.ru"]
    assert lead.name in mail.outbox[0].body


def test_notification_subject_contains_subject_title(machine):
    lead = LeadFactory(machine=machine)
    send_lead_notification(lead.pk, ["sales@modernmachinery.ru"])
    assert str(machine) in mail.outbox[0].subject


def test_notification_logs_event():
    lead = LeadFactory()
    send_lead_notification(lead.pk, ["sales@modernmachinery.ru"])
    assert lead.events.filter(kind=LeadEvent.Kind.EMAIL_SENT).exists()


def test_notification_records_failure(mocker):
    """Недоступность SMTP не должна терять заявку — она уже в базе."""
    lead = LeadFactory()
    mocker.patch(
        "apps.leads.tasks.EmailMultiAlternatives.send",
        side_effect=OSError("SMTP недоступен"),
    )

    with pytest.raises(Exception):  # noqa: B017  # Celery оборачивает ошибку в Retry
        send_lead_notification(lead.pk, ["sales@modernmachinery.ru"])

    assert lead.events.filter(kind=LeadEvent.Kind.EMAIL_FAILED).exists()
    assert Lead.objects.filter(pk=lead.pk).exists()


def test_purge_anonymizes_expired_leads():
    """Прямое требование 152-ФЗ о сроках хранения персональных данных."""
    expired = LeadFactory(
        name="Иванов Пётр",
        phone="+7 914 000-11-22",
        email="ivanov@example.com",
        company="ООО Ромашка",
        inn="2721000000",
        message="Нужен экскаватор",
        ip_address="203.0.113.5",
        user_agent="Mozilla/5.0",
        payload={"a": 1},
        purge_after=timezone.now().date() - datetime.timedelta(days=1),
    )

    assert purge_expired_leads() == 1

    expired.refresh_from_db()
    assert expired.name == ""
    assert expired.phone == ""
    assert expired.email == ""
    assert expired.company == ""
    assert expired.inn == ""
    assert expired.message == ""
    assert expired.ip_address is None
    assert expired.user_agent == ""
    assert expired.payload == {}
    assert expired.is_anonymized is True


def test_purge_keeps_the_record_itself():
    """Статистика по обращениям остаётся, персональные данные — нет."""
    lead = LeadFactory(purge_after=timezone.now().date() - datetime.timedelta(days=1))
    purge_expired_leads()

    assert Lead.objects.filter(pk=lead.pk).exists()
    assert lead.events.model.objects.filter(lead=lead, kind=LeadEvent.Kind.ANONYMIZED).exists()


def test_purge_skips_fresh_leads():
    LeadFactory(purge_after=timezone.now().date() + datetime.timedelta(days=10))
    assert purge_expired_leads() == 0


def test_purge_skips_leads_without_deadline():
    LeadFactory(purge_after=None)
    assert purge_expired_leads() == 0


def test_purge_is_idempotent():
    LeadFactory(purge_after=timezone.now().date() - datetime.timedelta(days=1))
    assert purge_expired_leads() == 1
    assert purge_expired_leads() == 0


@override_settings(LEADS_FALLBACK_EMAIL="office@modernmachinery.ru")
def test_notification_for_missing_lead_is_safe():
    assert send_lead_notification(999999, ["office@modernmachinery.ru"]) == "missing"
