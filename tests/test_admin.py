"""Тесты админки.

Критерий приёмки — контент-менеджер самостоятельно добавляет технику и новость,
поэтому проверяется, что страницы админки открываются и объект действительно
создаётся через форму.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

ADMIN_PAGES = [
    "catalog_brand",
    "catalog_category",
    "catalog_machinetype",
    "catalog_machine",
    "specs_specgroup",
    "specs_speckey",
    "parts_partcategory",
    "parts_part",
    "services_servicecategory",
    "services_service",
    "company_branch",
    "company_department",
    "company_employee",
    "content_page",
    "content_newspost",
    "content_vacancy",
    "content_menuitem",
    "content_sitesettings",
    "leads_lead",
    "leads_leadroutingrule",
    "leads_consentversion",
    "seo_redirectrule",
    "seo_notfoundlog",
    "imports_importrun",
    "imports_sourcepage",
    "users_user",
]


@pytest.mark.parametrize("page", ADMIN_PAGES)
def test_admin_changelist_opens(admin_client, page):
    assert admin_client.get(reverse(f"admin:{page}_changelist")).status_code == 200


@pytest.mark.parametrize(
    "page",
    [p for p in ADMIN_PAGES if p not in {"imports_importrun", "content_sitesettings"}],
)
def test_admin_add_form_opens(admin_client, page, branch):
    assert admin_client.get(reverse(f"admin:{page}_add")).status_code == 200


def test_import_run_cannot_be_created_by_hand(admin_client):
    """Прогоны импорта создаются командами, а не руками в админке."""
    assert admin_client.get(reverse("admin:imports_importrun_add")).status_code == 403


def test_anonymous_redirected_from_admin(client):
    response = client.get(reverse("admin:catalog_machine_changelist"))
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_regular_user_cannot_enter_admin(client, user):
    client.force_login(user)
    assert client.get(reverse("admin:catalog_machine_changelist")).status_code == 302


def test_content_manager_can_add_machine(admin_client, brand, machine_type):
    """Ключевой сценарий приёмки: техника заводится через админку."""
    from apps.catalog.models import Machine

    response = admin_client.post(
        reverse("admin:catalog_machine_add"),
        {
            "name": "PC490LC-11",
            "slug": "komatsu-pc490lc-11",
            "full_name": "",
            "series": "",
            "brand": brand.pk,
            "machine_type": machine_type.pk,
            "short_description": "",
            "description": "",
            "equipment": "",
            "warranty_note": "",
            "price_note": "",
            "is_price_on_request": "on",
            "is_published": "on",
            "is_active": "on",
            "sort_order": 100,
            "seo_title": "",
            "seo_description": "",
            "seo_h1": "",
            "raw_specs": "{}",
            "source_url": "",
            "source_hash": "",
            "images-TOTAL_FORMS": 0,
            "images-INITIAL_FORMS": 0,
            "specs-TOTAL_FORMS": 0,
            "specs-INITIAL_FORMS": 0,
            "documents-TOTAL_FORMS": 0,
            "documents-INITIAL_FORMS": 0,
            "stocks-TOTAL_FORMS": 0,
            "stocks-INITIAL_FORMS": 0,
        },
        follow=True,
    )

    assert response.status_code == 200
    assert Machine.objects.filter(slug="komatsu-pc490lc-11").exists()


def test_publish_action_publishes_machines(admin_client, machine):
    machine.is_published = False
    machine.save()

    admin_client.post(
        reverse("admin:catalog_machine_changelist"),
        {"action": "publish", "_selected_action": [machine.pk]},
        follow=True,
    )

    machine.refresh_from_db()
    assert machine.is_published is True


def test_unpublish_action(admin_client, machine):
    admin_client.post(
        reverse("admin:catalog_machine_changelist"),
        {"action": "unpublish", "_selected_action": [machine.pk]},
        follow=True,
    )
    machine.refresh_from_db()
    assert machine.is_published is False


@pytest.mark.parametrize(
    ("action", "expected"),
    [("mark_in_progress", "in_progress"), ("mark_done", "done"), ("mark_spam", "spam")],
)
def test_lead_status_actions(admin_client, action, expected):
    """Смена статуса заявки должна оставлять след в истории."""
    from apps.leads.factories import LeadFactory
    from apps.leads.models import LeadEvent

    lead = LeadFactory()
    admin_client.post(
        reverse("admin:leads_lead_changelist"),
        {"action": action, "_selected_action": [lead.pk]},
        follow=True,
    )

    lead.refresh_from_db()
    assert lead.status == expected
    assert lead.events.filter(kind=LeadEvent.Kind.STATUS_CHANGED).exists()


def test_notfound_resolve_action(admin_client):
    from apps.seo.models import NotFoundLog

    entry = NotFoundLog.objects.create(path="/staraya/")
    admin_client.post(
        reverse("admin:seo_notfoundlog_changelist"),
        {"action": "mark_resolved", "_selected_action": [entry.pk]},
        follow=True,
    )

    entry.refresh_from_db()
    assert entry.is_resolved is True


def test_site_settings_add_blocked_when_exists(admin_client):
    from apps.content.models import SiteSettings

    SiteSettings.load()
    assert admin_client.get(reverse("admin:content_sitesettings_add")).status_code == 403


def test_user_admin_shows_full_name(admin_client, user):
    response = admin_client.get(reverse("admin:users_user_changelist"))
    assert user.get_full_name() in response.content.decode()
