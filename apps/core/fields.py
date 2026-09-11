"""Поля моделей, общие для проекта."""

from django.db import models


class URLField(models.URLField):
    """URL-поле, форма которого достраивает адрес до https, а не до http.

    В Django 6.0 https станет схемой по умолчанию, а стандартное `URLField`
    до тех пор предупреждает об этом на каждой форме. Транзитная настройка
    `FORMS_URLFIELD_ASSUME_HTTPS` сама объявлена устаревшей, поэтому поведение
    задаётся явно на уровне поля — так оно переживёт обновление Django без
    правок.
    """

    def formfield(self, **kwargs):
        return super().formfield(**{"assume_scheme": "https", **kwargs})
