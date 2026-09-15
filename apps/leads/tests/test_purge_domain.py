"""Тесты очистки почтового домена из данных сайта.

Команда нужна демонстрационной площадке: наполнение заносило в базу адреса
настоящей компании, и заявка с демо-сайта однажды ушла в её почту.
"""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.company.factories import BranchContactFactory, EmployeeFactory
from apps.company.models import ContactPoint
from apps.content.models import SiteSettings
from apps.leads.factories import LeadRoutingRuleFactory
from apps.leads.models import LeadRoutingRule
from apps.users.factories import UserFactory

pytestmark = pytest.mark.django_db

DOMAIN = "modernmachinery.ru"


def purge(domain=DOMAIN, dry_run=False) -> str:
    out = StringIO()
    call_command("purge_email_domain", domain, dry_run=dry_run, stdout=out)
    return out.getvalue()


def test_purges_routing_rule_addresses(department):
    rule = LeadRoutingRuleFactory(
        department=department, emails=[f"sales@{DOMAIN}", "moy@yandex.ru"]
    )

    purge()

    rule.refresh_from_db()
    assert rule.emails == ["moy@yandex.ru"]


def test_purges_branch_contacts(branch):
    """Контакт показан на сайте ссылкой mailto — по ней пишут в компанию."""
    BranchContactFactory(branch=branch, kind=ContactPoint.Kind.EMAIL, value=f"khv@{DOMAIN}")
    BranchContactFactory(branch=branch, kind=ContactPoint.Kind.EMAIL, value="moy@yandex.ru")

    purge()

    assert list(ContactPoint.objects.values_list("value", flat=True)) == ["moy@yandex.ru"]


def test_purges_employee_email(branch):
    employee = EmployeeFactory(branch=branch, email=f"parts@{DOMAIN}")

    purge()

    employee.refresh_from_db()
    assert employee.email == ""


def test_purges_site_email(db):
    site = SiteSettings.load()
    site.main_email = f"khv@{DOMAIN}"
    site.save()

    purge()

    site.refresh_from_db()
    assert site.main_email == ""


def test_covers_subdomains(branch):
    BranchContactFactory(branch=branch, kind=ContactPoint.Kind.EMAIL, value=f"khv@filial.{DOMAIN}")

    purge()

    assert ContactPoint.objects.count() == 0


def test_keeps_other_domains(branch, department):
    BranchContactFactory(branch=branch, kind=ContactPoint.Kind.EMAIL, value="moy@yandex.ru")
    rule = LeadRoutingRuleFactory(department=department, emails=["moy@yandex.ru"])

    purge()

    rule.refresh_from_db()
    assert ContactPoint.objects.count() == 1
    assert rule.emails == ["moy@yandex.ru"]


def test_phone_contacts_are_untouched(branch):
    """Под очистку попадает почта, а не всё подряд."""
    BranchContactFactory(branch=branch, kind=ContactPoint.Kind.PHONE, value="+7 (4212) 45-67-00")

    purge()

    assert ContactPoint.objects.count() == 1


def test_dry_run_changes_nothing(branch, department):
    rule = LeadRoutingRuleFactory(department=department, emails=[f"sales@{DOMAIN}"])
    BranchContactFactory(branch=branch, kind=ContactPoint.Kind.EMAIL, value=f"khv@{DOMAIN}")

    report = purge(dry_run=True)

    rule.refresh_from_db()
    assert rule.emails == [f"sales@{DOMAIN}"]
    assert ContactPoint.objects.count() == 1
    assert "не сохранено" in report


def test_user_accounts_are_reported_not_changed():
    """Адрес учётной записи — это логин: очистка сломала бы вход."""
    user = UserFactory(email=f"admin@{DOMAIN}", receives_lead_emails=True)

    report = purge()

    user.refresh_from_db()
    assert user.email == f"admin@{DOMAIN}"
    assert user.username in report
    assert "подписан на заявки" in report


def test_reports_when_nothing_found(db):
    assert "не найдено" in purge()


def test_rejects_nonsense_domain(db):
    with pytest.raises(CommandError, match="не похоже на домен"):
        purge(domain="просто-строка")


def test_leaves_no_trace_of_the_domain(branch, department):
    """Сквозная проверка: после очистки домена в данных не остаётся."""
    BranchContactFactory(branch=branch, kind=ContactPoint.Kind.EMAIL, value=f"khv@{DOMAIN}")
    EmployeeFactory(branch=branch, email=f"parts@{DOMAIN}")
    LeadRoutingRuleFactory(department=department, emails=[f"sales@{DOMAIN}"])
    site = SiteSettings.load()
    site.main_email = f"office@{DOMAIN}"
    site.save()

    purge()

    leftovers = [
        *ContactPoint.objects.filter(value__endswith=DOMAIN),
        *[r for r in LeadRoutingRule.objects.all() if any(DOMAIN in a for a in r.emails)],
        *get_user_model().objects.none(),
    ]
    site.refresh_from_db()

    assert leftovers == []
    assert DOMAIN not in site.main_email
