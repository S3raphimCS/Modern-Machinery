"""Фоновые задачи по заявкам."""

from __future__ import annotations

import logging
from urllib.parse import urljoin

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
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
    if not recipients:
        # Получателей не осталось: их либо не настроили, либо все адреса
        # оказались на запрещённом домене. Подставлять резервный нельзя — он
        # уже проверен при подборе. Заявка в базе, в админке видна, письма нет.
        LeadEvent.objects.create(
            lead=lead,
            kind=LeadEvent.Kind.EMAIL_FAILED,
            comment="Некому отправить: получатели не настроены или запрещены",
        )
        logger.warning("Заявка %s: нет разрешённых получателей", lead_id)
        return "no-recipients"

    subject = f"Заявка с сайта: {lead.get_type_display()} — {lead.subject_title}"
    context = {
        "lead": lead,
        "subject": subject,
        # Ссылка собирается здесь, а не в шаблоне: у фоновой задачи нет запроса,
        # из которого можно было бы взять адрес сайта.
        "admin_url": urljoin(
            settings.SITE_URL,
            reverse("admin:leads_lead_change", args=[lead.pk]),
        ),
    }
    text_body = render_to_string("leads/email/notification.txt", context)
    html_body = render_to_string("leads/email/notification.html", context)

    try:
        # Обе версии в одном письме: клиент показывает оформленную, а текстовую
        # используют почтовые фильтры и те, кто отключил HTML. Письмо без
        # текстовой части заметно чаще уходит в спам.
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=False)
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
