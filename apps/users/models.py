"""Модель пользователя.

Собственная модель заводится с первого дня даже без личного кабинета: заменить
`auth.User` на живом проекте с историей — дорогая и рискованная операция, а
добавить поле в свою модель ничего не стоит.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Сотрудник филиала, работающий с сайтом и заявками."""

    email = models.EmailField("E-mail", unique=True)
    phone = models.CharField("Телефон", max_length=40, blank=True)
    position = models.CharField("Должность", max_length=200, blank=True)
    # Заявки распределяются по отделам, поэтому у пользователя есть отдел.
    department = models.ForeignKey(
        "company.Department",
        verbose_name="Отдел",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["username"]

    def __str__(self) -> str:
        return self.get_full_name() or self.username
