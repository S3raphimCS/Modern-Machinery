"""Тесты вложений к заявке.

Загрузка файлов посторонними — самая опасная часть публичной формы, поэтому
проверяется весь путь: приём, хранение, доступ, доставка менеджеру и
удаление по сроку.
"""

import datetime
import time
from pathlib import Path

import pytest
from django.core import mail, signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.leads.forms import FORM_TS_SALT
from apps.leads.models import Lead, LeadAttachment
from apps.leads.tasks import purge_expired_leads, send_lead_notification

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7\n" + b"x" * 500
XLSX = b"PK\x03\x04" + b"x" * 500


def upload(name="specifikaciya.pdf", content=PDF) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content)


def form_data(**overrides) -> dict:
    data = {
        "name": "Иванов Пётр",
        "phone": "+7 914 000-11-22",
        "consent": "1",
        "website": "",
        "form_ts": signing.dumps(time.time() - 10, salt=FORM_TS_SALT),
    }
    data.update(overrides)
    return data


def submit(client, files=None, **overrides):
    payload = form_data(**overrides)
    if files is not None:
        payload["attachments"] = files
    return client.post(reverse("content:lead-create", args=["parts"]), payload)


def test_file_is_attached_to_the_lead(client, branch, consent):
    response = submit(client, files=upload())

    assert response.status_code == 200
    attachment = LeadAttachment.objects.get()
    assert attachment.lead == Lead.objects.get()
    assert attachment.original_name == "specifikaciya.pdf"
    assert attachment.size == len(PDF)


def test_several_files_accepted(client, branch, consent):
    submit(client, files=[upload("tz.pdf"), upload("spisok.xlsx", XLSX)])

    assert LeadAttachment.objects.count() == 2


def test_more_than_limit_rejected(client, branch, consent):
    """Ограничение защищает и от случайной выгрузки всей папки."""
    response = submit(client, files=[upload(f"file{i}.pdf") for i in range(5)])

    assert response.status_code == 400
    assert LeadAttachment.objects.count() == 0


def test_disallowed_file_rejected_and_lead_not_created(client, branch, consent):
    response = submit(client, files=upload("virus.exe", b"MZ" + b"x" * 100))

    assert response.status_code == 400
    assert Lead.objects.count() == 0


def test_lead_without_files_still_works(client, branch, consent):
    """Вложение необязательно — большинство заявок приходит без файлов."""
    assert submit(client).status_code == 200
    assert Lead.objects.count() == 1
    assert LeadAttachment.objects.count() == 0


def test_stored_filename_is_random(client, branch, consent):
    """Имя от постороннего не попадает на диск: в нём может быть что угодно."""
    submit(client, files=upload("../../etc/passwd.pdf"))

    attachment = LeadAttachment.objects.get()
    assert "passwd" not in attachment.file.name
    assert ".." not in attachment.file.name
    assert attachment.file.name.startswith("leads/")


def test_file_has_no_public_url(client, branch, consent):
    """Документ клиента не должен открываться по угаданной ссылке."""
    submit(client, files=upload())
    attachment = LeadAttachment.objects.get()

    with pytest.raises(ValueError, match="публичного адреса"):
        _ = attachment.file.url


def test_download_requires_staff(client, branch, consent):
    submit(client, files=upload())
    attachment = LeadAttachment.objects.get()

    response = client.get(reverse("lead-attachment", args=[attachment.pk]))

    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_regular_user_cannot_download(client, branch, consent, user):
    submit(client, files=upload())
    attachment = LeadAttachment.objects.get()
    client.force_login(user)

    assert client.get(reverse("lead-attachment", args=[attachment.pk])).status_code == 302


def test_staff_downloads_the_file(admin_client, branch, consent, client):
    submit(client, files=upload())
    attachment = LeadAttachment.objects.get()

    response = admin_client.get(reverse("lead-attachment", args=[attachment.pk]))

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == PDF


def test_download_keeps_the_original_name(admin_client, branch, consent, client):
    submit(client, files=upload("Спецификация.pdf"))
    attachment = LeadAttachment.objects.get()

    response = admin_client.get(reverse("lead-attachment", args=[attachment.pk]))

    # Имена русские, поэтому в заголовке обязана быть версия по RFC 5987.
    # Регистр названия кодировки в ней не нормирован.
    disposition = response["Content-Disposition"].lower()
    assert "filename*=utf-8''" in disposition


@override_settings(PRIVATE_MEDIA_INTERNAL_URL="/protected-leads")
def test_nginx_serves_the_file_when_configured(admin_client, branch, consent, client):
    """Django проверяет права, а качает файл nginx — рабочий процесс свободен."""
    submit(client, files=upload())
    attachment = LeadAttachment.objects.get()

    response = admin_client.get(reverse("lead-attachment", args=[attachment.pk]))

    assert response["X-Accel-Redirect"] == f"/protected-leads/{attachment.file.name}"
    assert response.content == b""


def test_file_is_attached_to_the_email(client, branch, consent, department):
    from apps.leads.factories import LeadRoutingRuleFactory

    LeadRoutingRuleFactory(
        lead_type=Lead.Type.PARTS, department=department, emails=["parts@example.com"]
    )
    submit(client, files=upload())

    send_lead_notification(Lead.objects.get().pk, ["parts@example.com"])

    names = [name for name, _, _ in mail.outbox[0].attachments]
    assert "specifikaciya.pdf" in names


@override_settings(LEAD_EMAIL_ATTACHMENT_LIMIT=100)
def test_large_file_is_not_attached_but_letter_is_sent(client, branch, consent):
    """Письмо с неподъёмным вложением не дойдёт вовсе — а заявка важнее файла."""
    submit(client, files=upload())

    send_lead_notification(Lead.objects.get().pk, ["parts@example.com"])

    assert len(mail.outbox) == 1
    assert mail.outbox[0].attachments == []


def test_attachments_deleted_when_lead_is_anonymized(client, branch, consent):
    """Документы клиента — такие же персональные данные, срок хранения общий."""
    submit(client, files=upload())
    lead = Lead.objects.get()
    attachment = LeadAttachment.objects.get()
    path = Path(attachment.file.path)
    assert path.exists()

    Lead.objects.filter(pk=lead.pk).update(
        purge_after=timezone.now().date() - datetime.timedelta(days=1)
    )
    purge_expired_leads()

    assert LeadAttachment.objects.count() == 0
    assert not path.exists()


def test_deleting_attachment_removes_the_file(client, branch, consent):
    submit(client, files=upload())
    attachment = LeadAttachment.objects.get()
    path = Path(attachment.file.path)

    attachment.delete()

    assert not path.exists()


@pytest.mark.parametrize(
    ("size", "expected"),
    [(500, "500 Б"), (2048, "2 КБ"), (3 * 1024 * 1024, "3.0 МБ")],
)
def test_display_size_is_readable(size, expected, branch):
    """Менеджер видит размер человеческими единицами, а не числом байт."""
    from apps.leads.factories import LeadFactory

    attachment = LeadAttachment(lead=LeadFactory(), original_name="file.pdf", size=size)

    assert attachment.display_size == expected


def test_staff_without_lead_permission_cannot_download(client, branch, consent):
    """Признака сотрудника мало: нужен доступ именно к заявкам.

    У контент-менеджера, которому дали права только на новости, он тоже стоит
    — и перебором номеров он выкачал бы документы всех клиентов.
    """
    from apps.users.factories import UserFactory

    submit(client, files=upload())
    attachment = LeadAttachment.objects.get()

    editor = UserFactory(username="redaktor", is_staff=True)
    client.force_login(editor)

    assert client.get(reverse("lead-attachment", args=[attachment.pk])).status_code == 403


def test_staff_with_lead_permission_downloads(client, branch, consent):
    from django.contrib.auth.models import Permission

    from apps.users.factories import UserFactory

    submit(client, files=upload())
    attachment = LeadAttachment.objects.get()

    manager = UserFactory(username="menedzher", is_staff=True)
    manager.user_permissions.add(Permission.objects.get(codename="view_lead"))
    client.force_login(manager)

    assert client.get(reverse("lead-attachment", args=[attachment.pk])).status_code == 200


def test_files_removed_when_the_lead_is_deleted(client, branch, consent):
    """Удаление заявки в админке не должно оставлять документы на диске.

    Django удаляет связанные строки пакетным запросом, минуя метод объекта,
    поэтому файл убирает сигнал.
    """
    submit(client, files=upload())
    path = Path(LeadAttachment.objects.get().file.path)
    assert path.exists()

    Lead.objects.all().delete()

    assert LeadAttachment.objects.count() == 0
    assert not path.exists()


def test_repeat_submission_with_a_file_keeps_it(client, branch, consent):
    """Человек отправил заявку, вспомнил про спецификацию и отправил снова.

    Дедупликация не должна молча терять приложенный файл.
    """
    submit(client)
    assert LeadAttachment.objects.count() == 0

    response = submit(client, files=upload())

    assert response.status_code == 200
    assert Lead.objects.count() == 1
    assert LeadAttachment.objects.count() == 1
    assert LeadAttachment.objects.get().lead == Lead.objects.get()


def test_disposition_survives_a_quote_in_the_name(admin_client, branch, consent, client):
    """Кавычка в имени не должна разрывать заголовок на два параметра."""
    submit(client, files=upload('otchet".pdf'))
    attachment = LeadAttachment.objects.get()

    response = admin_client.get(reverse("lead-attachment", args=[attachment.pk]))
    disposition = response["Content-Disposition"]

    assert disposition.count("filename=") <= 1 or "filename*=" in disposition
    assert disposition.startswith("attachment;")


def test_stored_extension_comes_from_the_whitelist(client, branch, consent):
    """На диск попадает расширение из списка, а не то, что прислали."""
    from apps.leads.storage import attachment_upload_to

    path = attachment_upload_to(None, "a.%2e%2e%2Fpasswd")

    assert path.endswith(".bin")
    assert "%2e" not in path
