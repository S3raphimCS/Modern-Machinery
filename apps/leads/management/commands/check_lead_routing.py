"""Проверка, кому уйдут письма о заявках."""

from django.core.management.base import BaseCommand

from apps.leads.models import Lead
from apps.leads.services.routing import resolve_recipients


class Command(BaseCommand):
    help = (
        "Показывает, кто получит письмо по заявке каждого типа. Нужна, чтобы "
        "проверить настройку получателей, не отправляя заявку с сайта."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--type",
            dest="lead_type",
            choices=[value for value, _ in Lead.Type.choices],
            help="Проверить только один тип заявки.",
        )

    def handle(self, *args, **options) -> None:
        types = (
            [options["lead_type"]]
            if options["lead_type"]
            else [value for value, _ in Lead.Type.choices]
        )

        for lead_type in types:
            # Заявка не сохраняется: нужен только предмет для подбора правила.
            lead = Lead(type=lead_type)
            rule, recipients = resolve_recipients(lead)

            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{lead.get_type_display()}"))
            if rule is None:
                self.stdout.write(
                    self.style.WARNING("  правило маршрутизации не найдено — резервный адрес")
                )
            else:
                self.stdout.write(f"  правило: {rule.name}")
                self.stdout.write(f"  отдел:   {rule.department.name}")
            for address in recipients:
                self.stdout.write(f"  → {address}")

        self.stdout.write(
            "\nАдреса берутся из правил маршрутизации и из учётных записей "
            "с галочкой «Получать заявки на почту»."
        )
