"""Тесты калькулятора стоимости владения и модального окна заявки."""

import pytest

from apps.leads.models import Lead

pytestmark = pytest.mark.django_db

TCO_INPUT = {
    "hours_per_year": 1800,
    "fuel_consumption": "22",
    "fuel_price": "65",
    "maintenance_cost_year": "450000",
    "machine_price": "18000000",
    "lifetime_years": 7,
    "operator_cost_month": "120000",
}


def test_calculator_page_shows_form(client, branch):
    response = client.get("/kalkulyator/")
    assert response.status_code == 200
    assert response.context["form"] is not None


def test_calculation_returns_result(client, branch):
    response = client.post("/kalkulyator/", TCO_INPUT)
    result = response.context["result"]

    assert response.status_code == 200
    assert result.cost_per_hour > 0
    assert result.fuel_cost_year > 0


def test_calculation_via_htmx_returns_fragment(client, branch):
    response = client.post("/kalkulyator/", TCO_INPUT, HTTP_HX_REQUEST="true")
    names = [t.name for t in response.templates]

    assert "content/partials/tco_result.html" in names
    assert "base.html" not in names


def test_calculation_without_contacts_creates_no_lead(client, branch, consent):
    """Расчёт показывается всем: контакты в калькуляторе необязательны."""
    client.post("/kalkulyator/", TCO_INPUT)
    assert Lead.objects.count() == 0


def test_calculation_with_contacts_creates_lead(client, branch, consent):
    """Оставленные контакты превращают расчёт в заявку — это лид-магнит."""
    response = client.post(
        "/kalkulyator/", {**TCO_INPUT, "name": "Иванов", "phone": "+7 914 000-11-22"}
    )

    lead = Lead.objects.get()
    assert lead.type == Lead.Type.TCO
    assert lead.payload["result"]["cost_per_hour"] > 0
    assert lead.payload["input"]["hours_per_year"] == 1800
    assert response.context["created"] is True


def test_invalid_calculation_returns_errors(client, branch):
    response = client.post("/kalkulyator/", {**TCO_INPUT, "hours_per_year": 0})
    assert response.status_code == 400
    assert response.context["form"].errors


def test_lead_modal_rendered_for_known_type(client, branch):
    response = client.get("/zayavka/forma/", {"type": "service"})
    assert response.status_code == 200
    assert response.context["lead_type"] == "service"


def test_lead_modal_falls_back_to_default_type(client, branch):
    """Неизвестный тип из query-строки не должен ронять страницу."""
    response = client.get("/zayavka/forma/", {"type": "неизвестно"})

    assert response.status_code == 200
    assert response.context["lead_type"] == "price"


def test_unknown_lead_type_returns_404(client, branch, consent):
    assert client.post("/zayavka/nesuschestvuyuschiy-tip/", {}).status_code == 404


def test_lead_form_get_not_allowed(client, branch):
    assert client.get("/zayavka/price/").status_code == 405


def test_invalid_lead_form_returns_errors(client, branch, consent):
    response = client.post("/zayavka/price/", {"name": "", "consent": "1"})
    assert response.status_code == 400
    assert response.context["lead_form"].errors


def test_valid_lead_form_returns_success_fragment(client, branch, consent):
    import time

    from django.core import signing

    from apps.leads.forms import FORM_TS_SALT

    response = client.post(
        "/zayavka/price/",
        {
            "name": "Иванов",
            "phone": "+7 914 000-11-22",
            "consent": "1",
            "website": "",
            "form_ts": signing.dumps(time.time() - 10, salt=FORM_TS_SALT),
        },
    )

    assert response.status_code == 200
    assert "leads/partials/form_success.html" in [t.name for t in response.templates]
    assert Lead.objects.count() == 1


def test_service_lead_form_links_service(client, branch, consent):
    import time

    from django.core import signing

    from apps.leads.forms import FORM_TS_SALT
    from apps.services.factories import ServiceFactory

    service = ServiceFactory()
    client.post(
        "/zayavka/service/",
        {
            "name": "Иванов",
            "phone": "+7 914 000-11-33",
            "consent": "1",
            "website": "",
            "form_ts": signing.dumps(time.time() - 10, salt=FORM_TS_SALT),
            "service": service.pk,
        },
    )

    assert Lead.objects.get().service == service


def test_part_lead_form_links_part(client, branch, consent, brand):
    import time

    from django.core import signing

    from apps.leads.forms import FORM_TS_SALT
    from apps.parts.factories import PartFactory

    part = PartFactory(brand=brand)
    client.post(
        "/zayavka/parts/",
        {
            "name": "Иванов",
            "phone": "+7 914 000-11-44",
            "consent": "1",
            "website": "",
            "form_ts": signing.dumps(time.time() - 10, salt=FORM_TS_SALT),
            "part": part.pk,
        },
    )

    assert Lead.objects.get().part == part


def test_machine_lead_form_links_machine(client, branch, consent, machine):
    import time

    from django.core import signing

    from apps.leads.forms import FORM_TS_SALT

    client.post(
        "/zayavka/selection/",
        {
            "name": "Иванов",
            "phone": "+7 914 000-11-55",
            "consent": "1",
            "website": "",
            "form_ts": signing.dumps(time.time() - 10, salt=FORM_TS_SALT),
            "machine": machine.pk,
        },
    )

    lead = Lead.objects.get()
    assert lead.machine == machine
    assert lead.type == Lead.Type.SELECTION


def test_callback_form_requires_phone(client, branch, consent):
    """В коротком формате обратного звонка телефон обязателен."""
    from apps.leads.forms import CallbackForm

    form = CallbackForm(data={"name": "Иванов", "consent": True, "website": ""})
    assert not form.is_valid()
    assert "phone" in form.errors


def test_calculator_fields_use_project_styles(client, branch):
    """Поля обязаны нести класс проекта.

    Голый виджет Django выпадает из оформления сайта: у него нет ни рамки,
    ни отступов, ни поведения при фокусе.
    """
    content = client.get("/kalkulyator/").content.decode()

    assert content.count('class="mm-input"') >= 7
    assert 'name="hours_per_year" class="mm-input"' in content


def test_calculator_fields_are_grouped(client, branch):
    """Семь полей подряд читаются как анкета, три блока — как форма."""
    content = client.get("/kalkulyator/").content.decode()

    for title in ("Эксплуатация", "Затраты", "Машина"):
        assert f'mm-tco__legend">{title}' in content or title in content
    assert content.count("mm-tco__group") >= 4


def test_calculator_shows_units_next_to_fields(client, branch):
    """Единица измерения вынесена из подписи в суффикс поля."""
    content = client.get("/kalkulyator/").content.decode()

    assert 'mm-tco__unit">моточасов' in content
    assert 'mm-tco__unit">л/ч' in content
    assert 'mm-tco__unit">₽/л' in content
    # В подписи единицы остаться не должно.
    assert "Наработка в год, моточасов" not in content


def test_optional_fields_are_empty_by_default(client, branch):
    """Ноль в необязательном поле перекрывал подсказку и читался как заполнение."""
    content = client.get("/kalkulyator/").content.decode()

    assert 'name="machine_price" value="0"' not in content
    assert 'placeholder="18 000 000"' in content


def test_result_placeholder_before_calculation(client, branch):
    content = client.get("/kalkulyator/").content.decode()

    assert "mm-tco__placeholder" in content
    assert "появится стоимость часа работы" in content


def test_result_uses_grouped_digits(client, branch):
    """Шестизначные суммы без разделителей разрядов нечитаемы."""
    content = client.post("/kalkulyator/", TCO_INPUT).content.decode()

    # Неразрывный пробел между разрядами — формат русской локали.
    assert " " in content
    assert "mm-tco__total" in content


def test_form_groups_cover_every_field():
    """Ни одно поле не должно потеряться при группировке."""
    from apps.leads.forms import TcoForm

    form = TcoForm()
    grouped = {item["field"].name for group in form.grouped_fields() for item in group["fields"]}

    assert grouped == set(form.fields)


def test_form_units_match_fields():
    """Единица без поля — мёртвая запись, поле без единицы — потерянный смысл."""
    from apps.leads.forms import TcoForm

    assert set(TcoForm.UNITS) == set(TcoForm().fields)


def test_tco_lead_reports_a_goal(client, branch, consent, department):
    response = client.post(
        "/kalkulyator/", {**TCO_INPUT, "name": "Иванов", "phone": "+7 914 000-11-22"}
    )

    assert 'data-mm-goal-reached="lead_tco"' in response.content.decode()


def test_repeat_tco_lead_is_not_a_second_conversion(client, branch, consent, department):
    """И сообщение «заявка принята» при склейке больше не появляется."""
    data = {**TCO_INPUT, "name": "Иванов", "phone": "+7 914 000-11-22"}
    client.post("/kalkulyator/", data)

    body = client.post("/kalkulyator/", data).content.decode()

    assert Lead.objects.count() == 1
    assert "data-mm-goal-reached" not in body
    # Подтверждение обязано быть и при повторе: молчание в ответ выглядит как
    # сломанная кнопка.
    assert "Заявка принята" in body
    assert "мы уже получили её ранее" in body
