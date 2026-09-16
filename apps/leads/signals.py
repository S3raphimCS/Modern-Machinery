"""Сигналы заявок."""

import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import LeadAttachment

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=LeadAttachment)
def delete_attachment_file(sender, instance: LeadAttachment, **kwargs) -> None:
    """Удаляет файл с диска вслед за записью.

    Переопределённого `delete()` на модели недостаточно: при удалении заявки
    Django удаляет связанные строки пакетным запросом, минуя метод объекта.
    Без сигнала «Удалить выбранные» в админке заявок оставлял бы документы
    клиентов на диске навсегда — а это персональные данные с ограниченным
    сроком хранения.
    """
    if not instance.file:
        return
    try:
        instance.file.delete(save=False)
    except OSError:
        logger.warning("Не удалось удалить файл вложения %s", instance.pk)
