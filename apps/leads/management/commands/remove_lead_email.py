"""Удаление адреса из правил маршрутизации заявок."""

from django.core.management.base import BaseCommand

from apps.leads.models import LeadRoutingRule


class Command(BaseCommand):
    help = (
        "Убирает указанный адрес из всех правил маршрутизации заявок. "
        "Само правило остаётся: оно продолжает определять отдел, а письмо "
        "уйдёт подписчикам с галочкой «Получать заявки на почту»."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "addresses",
            nargs="+",
            help="Адреса, которые нужно убрать. Сравнение точное, без учёта регистра.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, что изменится, ничего не сохраняя.",
        )

    def handle(self, *args, **options) -> None:
        targets = {address.strip().casefold() for address in options["addresses"]}
        dry_run = options["dry_run"]
        changed = 0

        for rule in LeadRoutingRule.objects.order_by("priority", "name"):
            kept = [address for address in rule.emails if address.casefold() not in targets]
            if len(kept) == len(rule.emails):
                continue

            removed = [a for a in rule.emails if a.casefold() in targets]
            self.stdout.write(f"{rule.name}")
            self.stdout.write(self.style.WARNING(f"  убрано:  {', '.join(removed)}"))
            self.stdout.write(f"  осталось: {', '.join(kept) or '— (только подписчики)'}")

            if not dry_run:
                rule.emails = kept
                rule.save(update_fields=["emails"])
            changed += 1

        if not changed:
            self.stdout.write("Ни в одном правиле указанных адресов нет.")
            return

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(f"\nПробный запуск: изменений не сохранено ({changed} правил).")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"\nИзменено правил: {changed}."))
            self.stdout.write("Проверить, кому теперь уходят письма: manage.py check_lead_routing")
