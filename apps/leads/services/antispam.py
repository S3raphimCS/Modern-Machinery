"""Дедупликация заявок и проверка времени заполнения формы."""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.core.cache import cache

DEDUPE_KEY = "leads:dedupe:{digest}"


def build_fingerprint(
    *, lead_type: str, name: str, phone: str, email: str, message: str, ip: str | None
) -> str:
    """Строит отпечаток заявки для поиска повторной отправки.

    В отпечаток входит IP: две разные компании могут прислать одинаково
    выглядящую заявку «Иванов, нужен экскаватор», и глушить вторую нельзя.
    """
    payload = "|".join(
        [
            lead_type,
            name.strip().lower(),
            phone.strip(),
            email.strip().lower(),
            message.strip().lower(),
            ip or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_duplicate(fingerprint: str) -> int | None:
    """Возвращает id заявки, отправленной с тем же содержимым недавно."""
    return cache.get(DEDUPE_KEY.format(digest=fingerprint))


def remember(fingerprint: str, lead_id: int) -> None:
    """Запоминает отпечаток на время окна дедупликации."""
    cache.set(
        DEDUPE_KEY.format(digest=fingerprint),
        lead_id,
        settings.LEAD_DEDUPE_WINDOW_SECONDS,
    )
