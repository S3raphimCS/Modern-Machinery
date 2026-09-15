"""Создание администратора для разработки и демонстрации."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

DEFAULT_USERNAME = "admin"
# nosec B105 — это не секрет в коде, а значение по умолчанию для команды,
# которая при DEBUG=False отказывается работать.
DEFAULT_PASSWORD = "admin"  # noqa: S105  # nosec B105
DEFAULT_EMAIL = "admin@modernmachinery.example"


class Command(BaseCommand):
    help = (
        "Создаёт администратора с простым паролем для локальной работы и показа "
        "демо. В production выполнение заблокировано."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--username", default=DEFAULT_USERNAME)
        parser.add_argument("--password", default=DEFAULT_PASSWORD)
        parser.add_argument("--email", default=DEFAULT_EMAIL)
        parser.add_argument(
            "--force",
            action="store_true",
            help="Выполнить даже при DEBUG=False. Осознанное действие на свой риск.",
        )

    def handle(self, *args, **options) -> None:
        # Пароль «admin» на боевом сервере — это открытая дверь в админку,
        # поэтому команда по умолчанию работает только при DEBUG.
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "Отказано: команда создаёт администратора с заведомо слабым паролем "
                "и предназначена только для разработки. При DEBUG=False используйте "
                "createsuperuser, либо явно передайте --force."
            )

        user_model = get_user_model()
        username = options["username"]

        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={"email": options["email"]},
        )
        # Команда идемпотентна: повторный запуск чинит права и сбрасывает пароль,
        # а не падает с ошибкой уникальности.
        user.email = options["email"]
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(options["password"])
        user.save()

        action = "создан" if created else "обновлён"
        self.stdout.write(
            self.style.SUCCESS(
                f"Администратор {action}: логин «{username}», пароль «{options['password']}»."
            )
        )
