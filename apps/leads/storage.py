"""Хранилище приложенных к заявкам файлов.

Файлы лежат **вне** каталога media. Это сознательно: media раздаёт nginx
напрямую, и спецификация одного клиента открывалась бы по угаданной ссылке.
Класть их в media и потом закрывать правилом — значит защищаться запретом
поверх разрешения; здесь наоборот, по умолчанию доступа нет ни у кого.

Отдаёт файлы только представление с проверкой прав сотрудника.
"""

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage

from apps.leads.validators import ALLOWED_EXTENSIONS


class PrivateFileSystemStorage(FileSystemStorage):
    """Хранилище без публичного адреса."""

    def __init__(self, **kwargs):
        kwargs.setdefault("location", settings.PRIVATE_MEDIA_ROOT)
        # base_url намеренно не задан: попытка построить публичную ссылку
        # на такой файл должна падать, а не возвращать рабочий адрес.
        kwargs.setdefault("base_url", None)
        super().__init__(**kwargs)

    def url(self, name):  # pragma: no cover - защита от случайного вызова
        raise ValueError(
            "У приложенного к заявке файла нет публичного адреса. "
            "Ссылку выдаёт представление lead-attachment."
        )


private_storage = PrivateFileSystemStorage()


def attachment_upload_to(instance, filename: str) -> str:
    """Путь на диске: случайное имя вместо исходного.

    Исходное имя хранится отдельным полем и показывается менеджеру. На диске
    оно не используется: имя файла от постороннего — это и обход проверок
    через спецсимволы, и утечка содержимого через само название.
    """
    # Расширение сверяется с белым списком, а не просто обрезается: имя вида
    # «a.%2e%2e%2Fpasswd» дало бы на диске последовательность, которую nginx
    # раскодирует в переход по каталогам. Сегодня такое имя не проходит
    # проверку формы, но полагаться на это в имени файла не стоит.
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        extension = ".bin"
    return f"leads/{uuid.uuid4().hex}{extension}"
