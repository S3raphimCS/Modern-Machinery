"""Фоновые задачи по заявкам."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Lead, LeadEvent

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_lead_notification(self, lead_id: int, recipients: list[str]) -> str:
    """Отправляет письмо ответственным за заявку.

    Отправка вынесена в задачу, чтобы посетитель не ждал SMTP, а недоступность
    почтового сервера не приводила к потере заявки: она уже в базе.
    """
    lead = (
        Lead.objects.filter(pk=lead_id)
        .select_related("machine", "part", "service", "department")
        .first()
    )
    if lead is None:  # pragma: no cover
        logger.warning("Заявка %s не найдена, письмо не отправлено", lead_id)
        return "missing"
    if not recipients:  # pragma: no cover
        recipients = [settings.LEADS_FALLBACK_EMAIL]

    subject = f"Заявка с сайта: {lead.get_type_display()} — {lead.subject_title}"
    body = render_to_string("leads/email/notification.txt", {"lead": lead})

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception as exc:
        LeadEvent.objects.create(
            lead=lead, kind=LeadEvent.Kind.EMAIL_FAILED, comment=str(exc)[:500]
        )
        logger.exception("Не удалось отправить письмо по заявке %s", lead_id)
        raise self.retry(exc=exc) from exc

    LeadEvent.objects.create(
        lead=lead,
        kind=LeadEvent.Kind.EMAIL_SENT,
        comment="Отправлено: " + ", ".join(recipients),
    )
    return "sent"


@shared_task
def purge_expired_leads() -> int:
    """Обезличивает заявки с истёкшим сроком хранения персональных данных.

    Прямое требование 152-ФЗ о сроках хранения. Сама заявка не удаляется:
    статистика по обращениям остаётся, персональные данные — нет.
    """
    today = timezone.now().date()
    expired = Lead.objects.filter(purge_after__lt=today, is_anonymized=False)
    count = 0
    for lead in expired.iterator():
        lead.name = ""
        lead.company = ""
        lead.inn = ""
        lead.phone = ""
        lead.email = ""
        lead.message = ""
        lead.ip_address = None
        lead.user_agent = ""
        lead.payload = {}
        lead.is_anonymized = True
        lead.save(
            update_fields=[
                "name",
                "company",
                "inn",
                "phone",
                "email",
                "message",
                "ip_address",
                "user_agent",
                "payload",
                "is_anonymized",
                "updated_at",
            ]
        )
        LeadEvent.objects.create(
            lead=lead,
            kind=LeadEvent.Kind.ANONYMIZED,
            comment="Истёк срок хранения персональных данных",
        )
        count += 1
    if count:
        logger.info("Обезличено заявок: %s", count)
    return count
