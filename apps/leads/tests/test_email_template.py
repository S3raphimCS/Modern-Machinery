"""Тесты письма о заявке.

Вёрстка писем ломается тихо: отправка проходит, а получатель видит месиво.
Поэтому проверяются не только данные в письме, но и ограничения, которые
почтовые клиенты накладывают на разметку.
"""

import re

import pytest
from django.core import mail

from apps.leads.factories import LeadFactory
from apps.leads.tasks import send_lead_notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def sent(machine, department):
    lead = LeadFactory(
        name="Иванов Пётр",
        company="ООО Дальстрой",
        phone="+7 914 000-11-22",
        email="ivanov@dalstroy.ru",
        message="Нужен экскаватор до конца месяца",
        machine=machine,
        department=department,
    )
    send_lead_notification(lead.pk, ["sales@modernmachinery.ru"])
    return mail.outbox[0], lead


def html_part(message) -> str:
    return next(body for body, mime in message.alternatives if mime == "text/html")


def test_email_has_both_versions(sent):
    """Письмо без текстовой части заметно чаще уходит в спам."""
    message, _ = sent

    assert message.body.strip()
    assert len(message.alternatives) == 1
    assert message.alternatives[0][1] == "text/html"


def test_html_contains_lead_data(sent):
    message, lead = sent
    html = html_part(message)

    assert lead.name in html
    assert lead.company in html
    assert lead.phone in html
    assert lead.message in html
    assert str(lead.subject_title) in html


def test_text_version_contains_lead_data(sent):
    """Текстовую версию читают фильтры и те, кто отключил оформление."""
    message, lead = sent

    assert lead.name in message.body
    assert lead.phone in message.body


def test_both_versions_link_to_admin(sent):
    message, lead = sent
    expected = f"/admin/leads/lead/{lead.pk}/change/"

    assert expected in html_part(message)
    assert expected in message.body


def test_phone_is_a_callable_link(sent):
    """С телефона менеджер должен звонить в одно касание."""
    assert 'href="tel:+79140001122"' in html_part(sent[0])


def test_email_is_a_mailto_link(sent):
    assert 'href="mailto:ivanov@dalstroy.ru"' in html_part(sent[0])


def test_no_external_resources(sent):
    """Ни картинок, ни внешних стилей: клиенты блокируют и то, и другое."""
    html = html_part(sent[0])

    assert "<img" not in html
    assert 'rel="stylesheet"' not in html
    assert "@font-face" not in html
    assert "http://fonts" not in html and "https://fonts" not in html


def test_layout_uses_tables_not_modern_css(sent):
    """Outlook рисует письма движком Word: сетки и флексбоксы он не понимает."""
    html = html_part(sent[0])

    assert "<table" in html
    assert "display:flex" not in html
    assert "display:grid" not in html


def test_styles_are_inline(sent):
    """Часть клиентов вырезает блок <style> целиком."""
    html = html_part(sent[0])

    assert "<style" not in html
    assert html.count('style="') > 20


def test_has_preheader(sent):
    """Строка, которую клиент показывает в списке писем рядом с темой."""
    html = html_part(sent[0])

    assert "display:none" in html
    assert re.search(r"mso-hide\s*:\s*all", html)


def test_brand_colours_present(sent):
    html = html_part(sent[0])

    assert "#DD1C2B" in html
    assert "#16181C" in html


def test_optional_blocks_are_skipped(machine):
    """Пустые поля не оставляют в письме осиротевших подписей."""
    lead = LeadFactory(name="Без компании", company="", inn="", email="", message="")
    send_lead_notification(lead.pk, ["sales@modernmachinery.ru"])
    html = html_part(mail.outbox[0])

    assert "Компания" not in html
    assert "ИНН" not in html
    assert "Сообщение" not in html


def test_message_keeps_line_breaks(machine):
    lead = LeadFactory(message="Первая строка\nВторая строка")
    send_lead_notification(lead.pk, ["sales@modernmachinery.ru"])

    assert "<br>" in html_part(mail.outbox[0])
