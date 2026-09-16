"""Тесты подключения Яндекс.Метрики и отправки целей."""

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from apps.content.models import SiteSettings
from apps.leads.models import Lead

pytestmark = pytest.mark.django_db

COUNTER = "12345678"


def set_counter(value: str = COUNTER) -> None:
    settings_obj = SiteSettings.load()
    settings_obj.metrika_id = value
    settings_obj.save()


def page(client) -> str:
    return client.get("/").content.decode()


@override_settings(METRIKA_ENABLED=True)
def test_counter_appears_when_everything_lines_up(client, branch):
    set_counter()

    body = page(client)

    assert f'ym({COUNTER}, "init"' in body
    assert "mc.yandex.ru/metrika/tag.js" in body


@override_settings(METRIKA_ENABLED=True)
def test_counter_is_absent_without_a_number(client, branch):
    set_counter("")
    body = page(client)

    # Проверяется и то, что страница вообще отрисовалась: «нет упоминания
    # домена» прошло бы и при пустом ответе.
    assert "mm-footer" in body
    assert '"init"' not in body


@override_settings(METRIKA_ENABLED=True)
def test_non_numeric_number_is_refused(client, branch):
    """Значение уходит прямо в вызов JS, поэтому пропускаются только цифры."""
    set_counter("ym-12345; alert(1)")

    assert "alert(1)" not in page(client)
    assert "mc.yandex.ru" not in page(client)


@override_settings(METRIKA_ENABLED=False)
def test_flag_switches_the_counter_off(client, branch):
    set_counter()
    body = page(client)

    assert "mm-footer" in body
    assert '"init"' not in body


@override_settings(METRIKA_ENABLED=True)
def test_staff_are_not_counted(admin_client, branch):
    """На демо-стенде половина заходов наша — отчёты состояли бы из нас."""
    set_counter()

    assert "mc.yandex.ru" not in admin_client.get("/").content.decode()


@override_settings(METRIKA_ENABLED=True)
def test_counter_runs_under_a_nonce(client, branch):
    """Политика безопасности не допускает инлайновых скриптов без ключа."""
    set_counter()
    response = client.get("/")
    body = response.content.decode()

    nonce = response.wsgi_request.csp_nonce
    assert f'<script nonce="{nonce}">' in body


@override_settings(METRIKA_ENABLED=True)
def test_counter_is_included_exactly_once(client, branch):
    """В base.html лежал отдельный пиксель — он давал бы второй счёт."""
    set_counter()
    body = page(client)

    assert body.count('"init"') == 1
    # Считается именно пиксель счётчика: <noscript> на странице есть и у
    # фильтров каталога.
    assert body.count("mc.yandex.ru/watch/") == 1


@override_settings(METRIKA_ENABLED=True)
def test_number_entered_in_admin_is_visible_at_once(client, branch):
    """Настройки кешируются на десять минут — сохранение обязано сбросить кеш."""
    set_counter("")
    assert "mc.yandex.ru" not in page(client)

    set_counter("87654321")

    assert "ym(87654321" in page(client)


@override_settings(METRIKA_ENABLED=True)
def test_goal_script_is_loaded_with_the_counter(client, branch):
    set_counter()

    assert "js/metrika.js" in page(client)


@override_settings(METRIKA_ENABLED=False)
def test_goal_script_is_not_loaded_without_the_counter(client, branch):
    set_counter()

    assert "js/metrika.js" not in page(client)


def test_goal_marker_appears_when_a_lead_is_created(client, branch, consent, department):
    response = client.post(
        reverse("content:lead-create", args=["price"]),
        {"name": "Иван", "phone": "+7 914 771-05-42", "consent": "1"},
    )

    assert 'data-mm-goal-reached="lead_price"' in response.content.decode()


def test_repeat_submission_is_not_a_second_conversion(client, branch, consent, department):
    """Повтор склеивается с прежней заявкой, но экран успеха тот же."""
    data = {"name": "Иван", "phone": "+7 914 771-05-42", "consent": "1"}
    client.post(reverse("content:lead-create", args=["price"]), data)

    response = client.post(reverse("content:lead-create", args=["price"]), data)

    assert Lead.objects.count() == 1
    assert "data-mm-goal-reached" not in response.content.decode()


# Типы, у которых своя форма и свой партиал: они проверяются отдельно.
TYPES_WITH_OWN_FORM = {Lead.Type.TCO, Lead.Type.LEASING}


@pytest.mark.parametrize(
    "lead_type", sorted(set(Lead.Type.values) - {t.value for t in TYPES_WITH_OWN_FORM})
)
def test_every_lead_type_reports_its_goal(client, branch, consent, department, lead_type):
    """Новый тип заявки не должен тихо появиться без цели.

    Проверяется через вью, а не сверкой двух списков в самом тесте: маркер
    собирается строкой в шаблоне, и сверка списков ничего бы не доказала.
    """
    response = client.post(
        reverse("content:lead-create", args=[lead_type]),
        {"name": "Иван", "phone": "+7 914 771-05-42", "consent": "1"},
    )

    assert f'data-mm-goal-reached="lead_{lead_type}"' in response.content.decode()


def test_click_goals_are_not_reported_on_page_load(client, branch):
    """Ссылки на мессенджеры размечены целью — но цель по клику, не по показу.

    Общий атрибут у серверного маркера и у кликабельной ссылки приводил к
    тому, что `click_whatsapp` равнялся числу просмотров страницы.
    """
    settings_obj = SiteSettings.load()
    settings_obj.socials = {"whatsapp": "https://wa.me/79147710542"}
    settings_obj.save()

    body = page(client)

    assert 'data-mm-goal="click_whatsapp"' in body
    assert "data-mm-goal-reached" not in body


def test_marker_attribute_matches_the_script():
    """Атрибут в шаблонах и селектор в скрипте обязаны совпадать.

    Разъехавшись, они не сломают ни один серверный тест: в HTML маркер есть,
    а отправлять его некому.
    """
    script = (settings.BASE_DIR / "static" / "js" / "metrika.js").read_text()
    templates = settings.BASE_DIR / "templates"

    used = {
        attribute
        for path in templates.rglob("*.html")
        for attribute in ("data-mm-goal-reached", "data-mm-goal")
        if attribute in path.read_text()
    }

    for attribute in used:
        assert attribute in script, f"скрипт не знает про {attribute}"


def test_swapped_root_marker_is_not_missed():
    """Маркер может оказаться корнем подменяемого блока, а не его потомком.

    Форма заявки меняется с `hx-swap="outerHTML"`, поэтому корнями ответа
    становятся элементы верхнего уровня партиала — в том числе сам маркер.
    `querySelectorAll` ищет только среди потомков и такой маркер пропустит.
    """
    script = (settings.BASE_DIR / "static" / "js" / "metrika.js").read_text()

    assert "root.matches" in script, "скрипт обязан проверять сам корень"


@override_settings(METRIKA_ENABLED=True, METRIKA_WEBVISOR=False)
def test_webvisor_can_be_switched_off_without_touching_code(client, branch):
    """Запись сессий отключается переменной окружения.

    Запись содержимого полей отключается в кабинете Метрики, и если доступ к
    счётчику появится у кого-то ещё, это единственный рычаг на нашей стороне.
    """
    set_counter()

    assert "webvisor: false" in page(client)


@override_settings(METRIKA_ENABLED=True)
def test_webvisor_is_on_by_default(client, branch):
    set_counter()

    assert "webvisor: true" in page(client)
