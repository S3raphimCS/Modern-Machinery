"""Единая точка создания заявки.

И HTML-форма, и API проходят через эту функцию: правила о согласии, сроке
хранения, маршрутизации и дедупликации должны быть одинаковыми независимо от
того, откуда пришли данные.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.utils import get_client_ip
from apps.leads.models import ConsentVersion, Lead, LeadEvent

from . import antispam
from .routing import resolve_recipients

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")


def collect_request_meta(request) -> dict:
    """Собирает технический контекст заявки: источник, UTM, адрес, агент.

    Метки берутся из cookie, а не из адреса запроса: форма отправляется на
    `/zayavka/<тип>/` без параметров, и в самом запросе меток не бывает
    никогда. Адрес всё же читается — для заявок, созданных из API, где cookie
    нет, но параметры могут быть переданы напрямую.
    """
    if request is None:
        return {}

    from apps.leads.middleware import MAX_VALUE_LENGTH, read_marks

    utm = read_marks(request)
    # Длина режется и здесь: через API метка приходит параметром, минуя
    # посредника с его ограничением.
    utm.update(
        {key: request.GET[key][:MAX_VALUE_LENGTH] for key in UTM_KEYS if request.GET.get(key)}
    )
    return {
        "source_url": (request.META.get("HTTP_REFERER") or "")[:500],
        "referrer": (request.META.get("HTTP_REFERER") or "")[:500],
        "utm": utm,
        "ip_address": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:512],
    }


def attach_files(lead: Lead, files) -> None:
    """Привязывает загруженные файлы к заявке.

    Исходное имя сохраняется отдельным полем: на диске файл лежит под
    случайным именем, потому что название приходит от постороннего.
    """
    from apps.leads.models import LeadAttachment
    from apps.leads.validators import MAX_FILES_PER_LEAD

    for uploaded in list(files)[:MAX_FILES_PER_LEAD]:
        LeadAttachment.objects.create(
            lead=lead,
            file=uploaded,
            original_name=Path(uploaded.name).name[:255],
            size=uploaded.size,
        )


@transaction.atomic
def create_lead(
    *, data: dict, request=None, consent_given: bool = True, files=None
) -> tuple[Lead, bool]:
    """Создаёт заявку и запускает её обработку.

    Возвращает пару «заявка, создана ли она». Повторная отправка того же
    содержимого в пределах окна дедупликации возвращает уже существующую заявку
    с флагом False: посетитель видит успех, а в базе не появляется дубль.
    """
    meta = collect_request_meta(request)
    ip = meta.get("ip_address")

    fingerprint = antispam.build_fingerprint(
        lead_type=data.get("type", ""),
        name=data.get("name", ""),
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        message=data.get("message", ""),
        ip=ip,
    )
    duplicate_id = antispam.find_duplicate(fingerprint)
    if duplicate_id:
        existing = Lead.objects.filter(pk=duplicate_id).first()
        if existing is not None:
            # Повтор с файлом — обычное поведение: человек отправил заявку,
            # вспомнил про спецификацию и отправил снова. Молча потерять файл
            # нельзя, поэтому он прикрепляется к уже созданной заявке.
            if files:
                attach_files(existing, files)
            return existing, False

    consent = ConsentVersion.current() if consent_given else None
    retention = datetime.timedelta(days=settings.LEAD_RETENTION_DAYS)

    lead = Lead(**data)
    for field, value in meta.items():
        setattr(lead, field, value)
    if consent is not None:
        lead.consent = consent
        lead.consent_at = timezone.now()
    # Срок хранения проставляется сразу: иначе через год невозможно понять,
    # какие записи пора обезличивать.
    lead.purge_after = (timezone.now() + retention).date()

    rule, recipients = resolve_recipients(lead)
    if rule is not None:
        lead.department = rule.department
    lead.save()

    if files:
        attach_files(lead, files)

    LeadEvent.objects.create(lead=lead, kind=LeadEvent.Kind.CREATED)
    antispam.remember(fingerprint, lead.pk)

    from apps.leads.tasks import send_lead_notification

    # Письмо ставится в очередь после коммита: иначе воркер может взять задачу
    # раньше, чем транзакция дойдёт до базы, и не найти заявку.
    transaction.on_commit(lambda: send_lead_notification.delay(lead.pk, recipients))
    return lead, True
