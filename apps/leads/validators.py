"""Проверка файлов, приложенных к заявке.

Загрузка файлов посторонними — классическая точка входа для атаки, поэтому
проверок три и они дополняют друг друга:

1. Расширение из белого списка — отсекает очевидное.
2. Размер — защищает от переполнения диска.
3. Сигнатура содержимого — отсекает файл, которому просто переименовали
   расширение. Без неё скрипт, названный `spisok.pdf`, прошёл бы первую
   проверку.

Третья проверка сделана по сигнатурам, а не через определение типа
библиотекой: нужные форматы наперечёт, а лишняя зависимость в production —
лишняя поверхность для уязвимостей.
"""

from __future__ import annotations

from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

ALLOWED_EXTENSIONS = {
    ".pdf": "PDF",
    ".doc": "Word",
    ".docx": "Word",
    # Excel обязателен: списки артикулов снабженцы присылают именно так.
    ".xls": "Excel",
    ".xlsx": "Excel",
    ".jpg": "изображение",
    ".jpeg": "изображение",
    ".png": "изображение",
}

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_FILES_PER_LEAD = 3

# Сигнатуры начала файла для разрешённых форматов.
SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF", "pdf"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    # Старые Word и Excel — контейнер OLE2.
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole2"),
    # docx и xlsx — обычные zip-архивы.
    (b"PK\x03\x04", "zip"),
    (b"PK\x05\x06", "zip"),
    (b"PK\x07\x08", "zip"),
)

# Какие сигнатуры допустимы для какого расширения.
EXTENSION_SIGNATURES = {
    ".pdf": {"pdf"},
    ".doc": {"ole2", "zip"},
    ".docx": {"zip"},
    ".xls": {"ole2", "zip"},
    ".xlsx": {"zip"},
    ".jpg": {"jpeg"},
    ".jpeg": {"jpeg"},
    ".png": {"png"},
}


def detect_signature(head: bytes) -> str | None:
    """Определяет формат по первым байтам файла."""
    for magic, name in SIGNATURES:
        if head.startswith(magic):
            return name
    return None


@deconstructible
class LeadFileValidator:
    """Проверяет расширение, размер и фактическое содержимое файла."""

    def __call__(self, value) -> None:
        name = getattr(value, "name", "") or ""
        extension = Path(name).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise ValidationError(
                f"Файл такого типа приложить нельзя. Допустимые форматы: {allowed}."
            )

        size = getattr(value, "size", 0) or 0
        if size > MAX_FILE_SIZE:
            raise ValidationError(
                f"Файл больше {MAX_FILE_SIZE // 1024 // 1024} МБ. "
                "Пришлите его письмом или уменьшите размер."
            )
        if size == 0:
            raise ValidationError("Файл пустой.")

        head = self._read_head(value)
        signature = detect_signature(head)
        if signature is None or signature not in EXTENSION_SIGNATURES[extension]:
            raise ValidationError(
                "Содержимое файла не совпадает с его расширением. Проверьте, что файл не повреждён."
            )

    @staticmethod
    def _read_head(value, size: int = 16) -> bytes:
        """Читает начало файла, не сбивая последующее чтение."""
        position = value.tell() if hasattr(value, "tell") else 0
        try:
            value.seek(0)
            head = value.read(size)
        finally:
            value.seek(position)
        return head if isinstance(head, bytes) else bytes(head)

    def __eq__(self, other) -> bool:
        return isinstance(other, LeadFileValidator)
