"""Тесты команды создания администратора для разработки."""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

pytestmark = pytest.mark.django_db

User = get_user_model()


@override_settings(DEBUG=True)
def test_creates_superuser_with_defaults():
    call_command("create_dev_superuser", verbosity=0)

    user = User.objects.get(username="admin")
    assert user.is_superuser is True
    assert user.is_staff is True
    assert user.check_password("admin")


@override_settings(DEBUG=True)
def test_accepts_custom_credentials():
    call_command(
        "create_dev_superuser",
        username="manager",
        password="s3cret",
        email="manager@modernmachinery.ru",
        verbosity=0,
    )

    user = User.objects.get(username="manager")
    assert user.email == "manager@modernmachinery.ru"
    assert user.check_password("s3cret")


@override_settings(DEBUG=True)
def test_is_idempotent_and_repairs_rights():
    """Повторный запуск чинит права, а не падает на уникальности логина."""
    call_command("create_dev_superuser", verbosity=0)
    User.objects.filter(username="admin").update(is_staff=False, is_superuser=False)

    call_command("create_dev_superuser", verbosity=0)

    user = User.objects.get(username="admin")
    assert User.objects.filter(username="admin").count() == 1
    assert user.is_superuser is True
    assert user.is_staff is True


@override_settings(DEBUG=True)
def test_resets_password_on_repeat():
    call_command("create_dev_superuser", verbosity=0)
    call_command("create_dev_superuser", password="drugoy", verbosity=0)

    assert User.objects.get(username="admin").check_password("drugoy")


@override_settings(DEBUG=False)
def test_refuses_to_run_in_production():
    """Пароль «admin» на боевом сервере — открытая дверь в админку."""
    with pytest.raises(CommandError, match="Отказано"):
        call_command("create_dev_superuser", verbosity=0)

    assert User.objects.filter(username="admin").exists() is False


@override_settings(DEBUG=False)
def test_force_overrides_production_guard():
    call_command("create_dev_superuser", force=True, verbosity=0)
    assert User.objects.get(username="admin").is_superuser is True


def test_created_user_can_open_admin(client):
    """Созданной учётной записи действительно хватает прав на админку.

    Команда вызывается с --force, чтобы не включать DEBUG: под ним тестовые
    настройки подтянули бы панель отладки, которой в них нет.
    """
    call_command("create_dev_superuser", force=True, verbosity=0)
    assert client.login(username="admin", password="admin") is True

    response = client.get("/admin/")
    assert response.status_code == 200
    assert "Каталог техники" in response.content.decode()
