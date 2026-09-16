"""Тесты проверки приложенных файлов."""

import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.leads.validators import MAX_FILE_SIZE, LeadFileValidator, detect_signature

PDF = b"%PDF-1.7\n" + b"x" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 100
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 100
XLSX = b"PK\x03\x04" + b"x" * 100
DOC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"x" * 100

validate = LeadFileValidator()


def upload(name: str, content: bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content)


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("specifikaciya.pdf", PDF),
        ("foto.png", PNG),
        ("foto.jpg", JPEG),
        ("foto.jpeg", JPEG),
        ("spisok.xlsx", XLSX),
        ("spisok.xls", DOC),
        ("tz.doc", DOC),
        ("tz.docx", XLSX),
    ],
)
def test_allowed_files_pass(name, content):
    validate(upload(name, content))


@pytest.mark.parametrize(
    "name", ["virus.exe", "script.sh", "page.html", "vector.svg", "archive.zip", "noextension"]
)
def test_disallowed_extensions_rejected(name):
    with pytest.raises(ValidationError, match="Допустимые форматы"):
        validate(upload(name, PDF))


def test_renamed_file_is_rejected():
    """Скрипт, названный «spisok.pdf», не должен пройти проверку."""
    payload = b"#!/bin/sh\nrm -rf /\n" + b"x" * 100

    with pytest.raises(ValidationError, match="не совпадает"):
        validate(upload("spisok.pdf", payload))


def test_html_renamed_to_png_is_rejected():
    """Подменённая картинка могла бы выполнить скрипт на нашем домене."""
    with pytest.raises(ValidationError, match="не совпадает"):
        validate(upload("kartinka.png", b"<html><script>alert(1)</script></html>"))


def test_oversized_file_rejected():
    with pytest.raises(ValidationError, match="МБ"):
        validate(upload("bolshoy.pdf", b"%PDF" + b"x" * MAX_FILE_SIZE))


def test_empty_file_rejected():
    with pytest.raises(ValidationError, match="пустой"):
        validate(upload("pustoy.pdf", b""))


def test_extension_case_is_ignored():
    validate(upload("SPISOK.PDF", PDF))


def test_reading_head_does_not_disturb_later_reads():
    """После проверки файл должен читаться с начала — иначе он сохранится обрезанным."""
    stream = io.BytesIO(PDF)
    stream.name = "file.pdf"
    stream.size = len(PDF)

    validate(stream)

    assert stream.read() == PDF


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (PDF, "pdf"),
        (PNG, "png"),
        (JPEG, "jpeg"),
        (XLSX, "zip"),
        (DOC, "ole2"),
        (b"random bytes", None),
    ],
)
def test_signature_detection(head, expected):
    assert detect_signature(head) == expected
