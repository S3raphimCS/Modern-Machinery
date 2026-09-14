"""Модель пользователя.

Собственная модель заводится с первого дня даже без личного кабинета: заменить
`auth.User` на живом проекте с историей — дорогая и рискованная операция, а
добавить поле в свою модель ничего не стоит.
"""

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    """Менеджер пользователей с выборкой получателей заявок."""

    def lead_recipients(self, department=None):
        """Кому отправлять уведомления о новой заявке.

        Отбираются действующие сотрудники с включённой галочкой. Отдел сужает
        список: сотрудник, привязанный к отделу, получает только свои заявки,
        а сотрудник без отдела — все. Так руководитель видит поток целиком, а
        менеджер по запчастям не тонет в заявках на технику.

        Если у заявки отдела нет, уведомление уходит всем получателям: потерять
        заявку хуже, чем прислать её лишнему человеку.
        """
        recipients = self.filter(is_active=True, receives_lead_emails=True).exclude(email="")
        if department is not None:
            recipients = recipients.filter(
                models.Q(department__isnull=True) | models.Q(department=department)
            )
        return recipients


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

    receives_lead_emails = models.BooleanField(
        "Получать заявки на почту",
        default=False,
        help_text="Сотрудник будет получать письма о новых заявках. Если указан "
        "отдел, придут только заявки этого отдела; без отдела — все.",
    )

    objects = UserManager()

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["username"]
        constraints = [
            # Получатель без адреса — это молча потерянные заявки: письмо
            # отправить некуда, а в админке галочка стоит и выглядит рабочей.
            models.CheckConstraint(
                name="user_lead_recipient_needs_email",
                condition=models.Q(receives_lead_emails=False) | ~models.Q(email=""),
            )
        ]

    def __str__(self) -> str:
        return self.get_full_name() or self.username
