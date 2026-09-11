"""Тесты защиты формы заявок от автоматических отправок.

Капчи здесь нет намеренно: в РФ reCAPTCHA работает нестабильно, а на B2B-
аудитории заметно режет конверсию. Вместо неё несколько дешёвых проверок,
и каждая проверяется отдельно.
"""

import time

import pytest
from django.core import signing
from django.test import override_settings

from apps.leads.forms import FORM_TS_SALT, LeadForm

pytestmark = pytest.mark.django_db


def valid_ts(seconds_ago: float = 10) -> str:
    return signing.dumps(time.time() - seconds_ago, salt=FORM_TS_SALT)


def form_data(**overrides) -> dict:
    data = {
        "name": "Иванов Пётр",
        "phone": "+7 914 000-11-22",
        "consent": True,
        "website": "",
        "form_ts": valid_ts(),
    }
    data.update(overrides)
    return data


def test_valid_form_passes():
    assert LeadForm(data=form_data()).is_valid()


def test_filled_honeypot_rejects_submission():
    """Скрытое поле видит только бот — человек его не заполняет."""
    form = LeadForm(data=form_data(website="http://spam.example"))
    assert not form.is_valid()
    assert "website" in form.errors


@override_settings(LEAD_MIN_FORM_SECONDS=3)
def test_instant_submission_rejected():
    """Человек не заполняет форму за доли секунды."""
    form = LeadForm(data=form_data(form_ts=valid_ts(seconds_ago=0)))
    assert not form.is_valid()
    assert "form_ts" in form.errors


@override_settings(LEAD_MIN_FORM_SECONDS=3)
def test_slow_enough_submission_accepted():
    assert LeadForm(data=form_data(form_ts=valid_ts(seconds_ago=5))).is_valid()


def test_forged_timestamp_rejected():
    """Подделать подпись, не зная SECRET_KEY, нельзя."""
    form = LeadForm(data=form_data(form_ts="подделка"))
    assert not form.is_valid()
    assert "form_ts" in form.errors


def test_missing_timestamp_is_tolerated():
    """Отсутствие метки не блокирует отправку.

    Страница могла быть закеширована браузером до включения проверки — терять
    из-за этого живую заявку нельзя.
    """
    assert LeadForm(data=form_data(form_ts="")).is_valid()


def test_contact_required():
    form = LeadForm(data=form_data(phone="", email=""))
    assert not form.is_valid()
    assert "Укажите телефон или e-mail" in str(form.errors)


def test_email_alone_is_enough():
    assert LeadForm(data=form_data(phone="", email="buyer@example.com")).is_valid()


def test_consent_required():
    """Без согласия на обработку ПДн заявка не принимается — требование 152-ФЗ."""
    form = LeadForm(data=form_data(consent=False))
    assert not form.is_valid()
    assert "consent" in form.errors


def test_form_provides_fresh_timestamp():
    form = LeadForm()
    value = form.fields["form_ts"].initial
    assert time.time() - float(signing.loads(value, salt=FORM_TS_SALT)) < 5
