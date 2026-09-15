"""Полная очистка почтового домена из данных сайта."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Убирает все адреса указанного домена отовсюду: из правил маршрутизации, "
        "контактов филиала и сотрудников, настроек сайта. Нужна демонстрационной "
        "площадке, куда демо-данные занесли адреса настоящей компании."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("domain", help="Домен, например modernmachinery.ru")
        parser.add_argument(
            "--dry-run", action="store_true", help="Показать, что изменится, ничего не сохраняя."
        )

    def handle(self, *args, **options) -> None:
        from apps.company.models import ContactPoint, Employee
        from apps.content.models import SiteSettings
        from apps.leads.models import LeadRoutingRule

        domain = options["domain"].strip().casefold().lstrip("@")
        if not domain or "." not in domain:
            raise CommandError(f"«{options['domain']}» не похоже на домен")
        dry_run = options["dry_run"]

        def matches(address: str) -> bool:
            value = (address or "").casefold()
            if "@" not in value:
                return False
            host = value.rsplit("@", 1)[1]
            return host == domain or host.endswith(f".{domain}")

        with transaction.atomic():
            total = 0

            # 1. Правила маршрутизации — сюда уходят письма о заявках.
            for rule in LeadRoutingRule.objects.order_by("name"):
                kept = [a for a in rule.emails if not matches(a)]
                if len(kept) != len(rule.emails):
                    removed = [a for a in rule.emails if matches(a)]
                    self.stdout.write(f"правило «{rule.name}»: {', '.join(removed)}")
                    if not dry_run:
                        rule.emails = kept
                        rule.save(update_fields=["emails"])
                    total += 1

            # 2. Контакты филиала и сотрудников — они показаны на сайте
            #    ссылкой mailto, по которой посетитель может написать.
            contacts = [c for c in ContactPoint.objects.all() if matches(c.value)]
            for contact in contacts:
                owner = contact.employee or contact.branch
                self.stdout.write(f"контакт {contact.value} ({owner})")
                if not dry_run:
                    contact.delete()
                total += 1

            for employee in Employee.objects.exclude(email=""):
                if matches(employee.email):
                    self.stdout.write(f"почта сотрудника {employee.full_name}: {employee.email}")
                    if not dry_run:
                        employee.email = ""
                        employee.save(update_fields=["email"])
                    total += 1

            # 3. Общая почта в подвале и на странице контактов.
            site = SiteSettings.objects.first()
            if site and matches(site.main_email):
                self.stdout.write(f"почта сайта: {site.main_email}")
                if not dry_run:
                    site.main_email = ""
                    site.save()
                total += 1

            if dry_run:
                transaction.set_rollback(True)

        # 4. Учётные записи не трогаем: адрес там — это логин, и очистка
        #    сломала бы вход. Только предупреждаем.
        self._warn_about_users(matches)

        if not total:
            self.stdout.write(f"Адресов на домене {domain} не найдено.")
        elif dry_run:
            self.stdout.write(
                self.style.NOTICE(f"\nПробный запуск: изменений не сохранено ({total}).")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"\nУбрано записей: {total}."))
            self.stdout.write(
                "Чтобы адреса не вернулись, добавьте домен в LEADS_BLOCKED_EMAIL_DOMAINS."
            )

    def _warn_about_users(self, matches) -> None:
        from django.contrib.auth import get_user_model

        affected = [u for u in get_user_model().objects.exclude(email="") if matches(u.email)]
        if not affected:
            return

        self.stdout.write(
            self.style.WARNING(
                "\nУчётные записи с адресом на этом домене (не изменены — это логин):"
            )
        )
        for user in affected:
            note = " — подписан на заявки" if user.receives_lead_emails else ""
            self.stdout.write(f"  {user.username}: {user.email}{note}")
