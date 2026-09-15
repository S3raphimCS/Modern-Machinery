"""Генератор демонстрационного наполнения.

Команда идемпотентна и детерминирована: повторный запуск не создаёт дублей, а
одинаковый seed даёт одинаковые данные. Это важно и для демонстрации, и для
тестов — выдача каталога не должна меняться от прогона к прогону.
"""

from __future__ import annotations

import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.models import Brand, Category, Machine, MachineStock, MachineType
from apps.company.models import Branch, ContactPoint, Department, Employee
from apps.content.models import (
    MenuItem,
    NewsCategory,
    NewsPost,
    Page,
    SiteSettings,
    Vacancy,
)
from apps.core.utils import slugify_ru
from apps.imports import demo_data as data
from apps.imports.models import ImportRun
from apps.leads.models import ConsentVersion, LeadRoutingRule
from apps.parts.models import Part, PartApplicability, PartCategory, PartStock
from apps.services.models import Service, ServiceCategory
from apps.specs.models import MachineSpec, SpecGroup, SpecKey, SpecOption


class Command(BaseCommand):
    help = "Наполняет базу демонстрационными данными филиала в Хабаровске."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--seed",
            type=int,
            default=20260910,
            help="Зерно генератора: одинаковое значение даёт одинаковые данные.",
        )
        parser.add_argument(
            "--parts",
            type=int,
            default=240,
            help="Сколько позиций запчастей создать.",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Не печатать ход выполнения.",
        )
        parser.add_argument(
            "--no-images",
            action="store_true",
            help="Не генерировать изображения-заглушки. Заметно быстрее: "
            "рисование и сжатие сотни картинок занимает больше времени, "
            "чем всё остальное наполнение вместе взятое.",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        # nosec B311 — генератор нужен воспроизводимый, а не криптостойкий:
        # демо-данные обязаны совпадать от прогона к прогону.
        self.rng = random.Random(options["seed"])  # nosec B311
        self.quiet = options["quiet"]
        self.with_images = not options["no_images"]
        run = ImportRun.objects.create(source="demo", kind="seed_demo")

        stats = {}
        branch = self._create_company()
        stats["departments"] = Department.objects.count()
        brands = self._create_brands()
        categories = self._create_categories()
        types = self._create_machine_types()
        spec_keys = self._create_specs()
        stats["machines"] = self._create_machines(brands, categories, types, spec_keys, branch)
        stats["parts"] = self._create_parts(brands, branch, options["parts"])
        stats["services"] = self._create_services()
        stats["content"] = self._create_content(branch)
        stats["landings"] = self._create_landings()
        self._create_lead_rules()

        run.finish(status=ImportRun.Status.SUCCESS, stats=stats)
        if not self.quiet:
            self.stdout.write(
                self.style.SUCCESS(
                    "Демо-данные готовы: "
                    f"{stats['machines']} машин, {stats['parts']} запчастей, "
                    f"{stats['services']} услуг."
                )
            )

    def _say(self, message: str) -> None:
        if not self.quiet:
            self.stdout.write(message)

    # --- Компания ---------------------------------------------------------

    def _create_company(self) -> Branch:
        branch, _ = Branch.objects.update_or_create(
            slug="khabarovsk",
            defaults={
                "city": "Хабаровск",
                "address": "ул. Промышленная, 20",
                "postcode": "680031",
                "latitude": Decimal("48.443800"),
                "longitude": Decimal("135.093000"),
                "timezone": "Asia/Vladivostok",
                "work_hours": "Пн–Сб 9:00–18:00",
                "description": (
                    "Филиал «Модерн Машинери Фар Ист» в Хабаровске: продажа техники "
                    "Komatsu, BOMAG, Manitou, склад запасных частей и собственный "
                    "сервисный центр с выездом на объект."
                ),
                "is_published": True,
                "published_at": timezone.now(),
                "seo_title": "Модерн Машинери в Хабаровске — техника, запчасти, сервис",
                "seo_description": (
                    "Официальный дистрибьютор Komatsu в Хабаровске: спецтехника, "
                    "оригинальные запчасти, сервисный центр и выезд на объект."
                ),
            },
        )
        for kind, value, ext in [
            ("phone", "+7 (4212) 45-67-00", ""),
            ("email", "khv@modernmachinery.ru", ""),
            ("whatsapp", "+7 (914) 771-05-42", ""),
            ("telegram", "@modernmachinery_khv", ""),
        ]:
            ContactPoint.objects.get_or_create(
                branch=branch, kind=kind, value=value, defaults={"extension": ext}
            )

        for order, (code, name, email) in enumerate(data.DEPARTMENTS, start=1):
            Department.objects.update_or_create(
                code=code, defaults={"name": name, "sort_order": order * 10}
            )
            self._department_emails = getattr(self, "_department_emails", {})
            self._department_emails[code] = email

        for order, (full_name, position, dept_code, contacts) in enumerate(data.EMPLOYEES, 1):
            department = Department.objects.filter(code=dept_code).first() if dept_code else None
            employee, _ = Employee.objects.update_or_create(
                full_name=full_name,
                branch=branch,
                defaults={
                    "position": position,
                    "department": department,
                    "is_published": True,
                    "published_at": timezone.now(),
                    "sort_order": order * 10,
                },
            )
            for kind, value, ext in contacts:
                ContactPoint.objects.get_or_create(
                    employee=employee, kind=kind, value=value, defaults={"extension": ext}
                )
        self._say(f"Филиал и {len(data.EMPLOYEES)} сотрудников готовы.")
        return branch

    # --- Справочники каталога --------------------------------------------

    def _create_brands(self) -> dict[str, Brand]:
        brands = {}
        for order, (slug, name, description) in enumerate(data.BRANDS, start=1):
            brand, _ = Brand.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": description,
                    "is_active": True,
                    "sort_order": order * 10,
                },
            )
            brands[slug] = brand
        return brands

    def _create_categories(self) -> dict[str, Category]:
        categories = {}
        for slug, name, children in data.CATEGORIES:
            root = Category.objects.filter(slug=slug).first()
            if root is None:
                root = Category.objects.add_root({"slug": slug, "name": name, "is_active": True})
            categories[slug] = root
            for child_slug, child_name in children:
                child = Category.objects.filter(slug=child_slug).first()
                if child is None:
                    root = Category.objects.get(pk=root.pk)
                    child = Category.objects.add_child(
                        root,
                        {"slug": child_slug, "name": child_name, "is_active": True},
                    )
                categories[child_slug] = child
        return categories

    def _create_machine_types(self) -> dict[str, MachineType]:
        types = {}
        for order, (slug, name, plural) in enumerate(data.MACHINE_TYPES, start=1):
            machine_type, _ = MachineType.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "name_plural": plural, "sort_order": order * 10},
            )
            types[slug] = machine_type
        return types

    def _create_specs(self) -> dict[str, SpecKey]:
        groups = {}
        for code, name, order in data.SPEC_GROUPS:
            group, _ = SpecGroup.objects.update_or_create(
                code=code, defaults={"name": name, "sort_order": order}
            )
            groups[code] = group

        keys = {}
        for order, row in enumerate(data.SPEC_KEYS, start=1):
            code, name, group_code, unit, value_type, filterable, in_card, decimals, aliases = row
            key, _ = SpecKey.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "group": groups[group_code],
                    "unit": unit,
                    "value_type": value_type,
                    "is_filterable": filterable,
                    "is_in_card": in_card,
                    "decimals": decimals,
                    "aliases": aliases,
                    "sort_order": order * 10,
                },
            )
            keys[code] = key

        for key_code, options in data.SPEC_OPTIONS.items():
            for order, (option_code, option_name) in enumerate(options, start=1):
                SpecOption.objects.update_or_create(
                    spec_key=keys[key_code],
                    code=option_code,
                    defaults={"name": option_name, "sort_order": order * 10},
                )

        # Привязка параметров к типам техники: контент-менеджер видит в карточке
        # только те поля, которые к этой машине вообще применимы.
        for type_slug, codes in data.TYPE_SPECS.items():
            machine_type = MachineType.objects.get(slug=type_slug)
            for code in codes:
                keys[code].machine_types.add(machine_type)
        return keys

    # --- Техника ----------------------------------------------------------

    def _spec_value(self, code: str, bounds: tuple, decimals: int):
        low, high = bounds
        if decimals == 0:
            step = max(1, int((high - low) // 50))
            return Decimal(self.rng.randrange(int(low), int(high), step))
        value = self.rng.uniform(float(low), float(high))
        return Decimal(f"{value:.{decimals}f}")

    def _create_machines(self, brands, categories, types, spec_keys, branch) -> int:
        created = 0
        engine_models = [
            "SAA6D107E-1",
            "SAA6D114E-3",
            "SAA6D125E-5",
            "SAA12V140E-3",
            "Deutz TCD 3.6 L4",
            "Kubota V3307",
            "Perkins 1104D-44TA",
        ]
        for brand_slug, type_slug, category_slug, models in data.MACHINE_LINES:
            brand = brands[brand_slug]
            machine_type = types[type_slug]
            category = categories[category_slug]
            ranges = data.SPEC_RANGES[type_slug]

            for model_name in models:
                slug = slugify_ru(f"{brand.name}-{model_name}")
                full_name = f"{machine_type.name} {brand.name} {model_name}"
                machine, _ = Machine.objects.update_or_create(
                    slug=slug,
                    defaults={
                        "name": model_name,
                        "full_name": full_name,
                        "series": model_name.split("-")[0],
                        "brand": brand,
                        "machine_type": machine_type,
                        "short_description": (
                            f"{full_name} — поставка со склада в Хабаровске, "
                            f"гарантия и сервисное обслуживание."
                        ),
                        "description": (
                            f"{full_name}. Техника поставляется официальным дистрибьютором "
                            f"с полным пакетом документов. Обслуживание выполняет сервисный "
                            f"центр филиала в Хабаровске: плановое ТО, ремонт узлов, выезд "
                            f"на объект. Оригинальные запасные части — на складе."
                        ),
                        "equipment": (
                            "Кабина с кондиционером и отопителем, защита днища, "
                            "предпусковой подогреватель, комплект инструмента."
                        ),
                        "warranty_note": "12 месяцев или 2000 моточасов",
                        "is_published": True,
                        "published_at": timezone.now(),
                        "is_active": True,
                        "seo_title": f"{full_name} купить в Хабаровске — цена, характеристики",
                        "seo_description": (
                            f"{full_name}: технические характеристики, наличие на складе "
                            f"в Хабаровске, сервисное обслуживание и запчасти."
                        ),
                    },
                )
                machine.categories.add(category)

                # Часть позиций с ценой, остальные «по запросу» — так карточка
                # в макете показывает оба состояния.
                if self.rng.random() < 0.35:
                    machine.price = Decimal(self.rng.randrange(4_500_000, 68_000_000, 100_000))
                    machine.is_price_on_request = False
                    machine.price_note = "с НДС, склад Хабаровск"
                    machine.save(update_fields=["price", "is_price_on_request", "price_note"])

                self._create_machine_specs(machine, type_slug, ranges, spec_keys, engine_models)
                self._create_machine_stock(machine, branch)
                if self.with_images:
                    self._create_machine_image(machine)
                created += 1
        self._say(f"Создано моделей техники: {created}.")
        return created

    def _create_machine_specs(self, machine, type_slug, ranges, spec_keys, engine_models):
        for code in data.TYPE_SPECS[type_slug]:
            key = spec_keys[code]
            spec = MachineSpec(machine=machine, spec_key=key)

            if key.value_type == SpecKey.ValueType.NUMBER:
                if code not in ranges:
                    continue
                value = self._spec_value(code, ranges[code], key.decimals)
                spec.value_num = value
                # Часть параметров — диапазоны: у экскаваторов это норма,
                # и фильтр обязан их учитывать.
                if code in {"digging_depth", "lift_height"} and self.rng.random() < 0.4:
                    spec.value_num_max = value + Decimal(f"{self.rng.uniform(0.3, 1.2):.1f}")
                    spec.raw_value = f"{spec.value_num}–{spec.value_num_max} {key.unit}"
                else:
                    spec.raw_value = f"{value} {key.unit}".strip()
            elif key.value_type == SpecKey.ValueType.STRING:
                spec.value_str = self.rng.choice(engine_models)
                spec.raw_value = spec.value_str
            elif key.value_type == SpecKey.ValueType.BOOL:
                spec.value_bool = self.rng.random() < 0.85
                spec.raw_value = "Есть" if spec.value_bool else "Нет"
            elif key.value_type == SpecKey.ValueType.OPTION:
                options = list(key.options.all())
                if not options:
                    continue
                if code == "track_type":
                    gusenichnye = {"ekskavator", "bulldozer"}
                    wanted = "gusenichnaya" if type_slug in gusenichnye else "kolesnaya"
                    option = next((o for o in options if o.code == wanted), options[0])
                else:
                    option = self.rng.choice(options)
                spec.value_option = option
                spec.raw_value = option.name

            MachineSpec.objects.update_or_create(
                machine=machine,
                spec_key=key,
                defaults={
                    "value_num": spec.value_num,
                    "value_num_max": spec.value_num_max,
                    "value_str": spec.value_str,
                    "value_bool": spec.value_bool,
                    "value_option": spec.value_option,
                    "raw_value": spec.raw_value,
                },
            )

    def _create_machine_image(self, machine) -> None:
        """Заводит карточке изображение-заглушку.

        Реальных фотографий у демонстрационного наполнения нет, а пустая плитка
        читается как поломка вёрстки. Заглушка с моделью и типом техники честно
        сообщает «фото пока нет» и не портит впечатление от каталога.
        Производные в WebP и превью соберутся сигналом сохранения.
        """
        from django.core.files.base import ContentFile

        from apps.catalog.models import MachineImage
        from apps.catalog.services.images import make_placeholder

        if machine.images.exists():
            return

        payload = make_placeholder(
            title=f"{machine.brand.name} {machine.name}",
            subtitle=f"{machine.machine_type.name} · Хабаровск",
        )
        image = MachineImage(
            machine=machine,
            alt=f"{machine.full_name} — фотография",
            is_main=True,
            sort_order=10,
        )
        image.image.save(f"{machine.slug}.jpg", ContentFile(payload), save=False)
        image.save()

    def _create_machine_stock(self, machine, branch) -> None:
        roll = self.rng.random()
        if roll < 0.45:
            status, quantity, lead = MachineStock.Status.IN_STOCK, self.rng.randint(1, 4), "1–2 дня"
        elif roll < 0.6:
            status, quantity, lead = MachineStock.Status.LOW, 1, "3–5 дней"
        else:
            status, quantity, lead = MachineStock.Status.ON_ORDER, None, "45–60 дней"
        MachineStock.objects.update_or_create(
            machine=machine,
            branch=branch,
            defaults={
                "status": status,
                "quantity": quantity,
                "lead_time": lead,
                "synced_at": timezone.now(),
            },
        )

    # --- Запчасти ---------------------------------------------------------

    def _create_parts(self, brands, branch, target: int) -> int:
        categories = {}
        for slug, name in data.PART_CATEGORIES:
            category = PartCategory.objects.filter(slug=slug).first()
            if category is None:
                category = PartCategory.objects.add_root(
                    {"slug": slug, "name": name, "is_active": True}
                )
            categories[slug] = category

        machines = list(Machine.objects.all()[:60])
        created = 0
        number = 1000
        while created < target:
            for category_slug, templates in data.PART_TEMPLATES.items():
                if created >= target:
                    break
                category = categories[category_slug]
                for name_template, article_template in templates:
                    if created >= target:
                        break
                    number += 7
                    article = article_template.format(n=number)
                    brand = brands["techking"] if category_slug == "shiny" else brands["komatsu"]
                    part, _ = Part.objects.update_or_create(
                        brand=brand,
                        article=article,
                        defaults={
                            "name": name_template,
                            "category": category,
                            "description": (
                                f"{name_template}, оригинальная деталь {brand.name}. "
                                f"Наличие уточняйте на складе в Хабаровске."
                            ),
                            "is_original": category_slug != "shiny",
                            "is_published": True,
                            "is_active": True,
                            "weight_kg": Decimal(f"{self.rng.uniform(0.2, 180):.3f}"),
                        },
                    )
                    self._create_part_stock(part, branch)
                    for machine in self.rng.sample(machines, k=min(3, len(machines))):
                        PartApplicability.objects.get_or_create(part=part, machine=machine)
                    created += 1
        self._say(f"Создано позиций запчастей: {created}.")
        return created

    def _create_part_stock(self, part, branch) -> None:
        roll = self.rng.random()
        if roll < 0.55:
            status, quantity, lead = PartStock.Status.IN_STOCK, self.rng.randint(3, 40), ""
        elif roll < 0.7:
            status, quantity, lead = PartStock.Status.LOW, self.rng.randint(1, 2), ""
        else:
            status, quantity, lead = PartStock.Status.ON_ORDER, 0, "14–21 день"
        PartStock.objects.update_or_create(
            part=part,
            branch=branch,
            defaults={
                "status": status,
                "quantity": quantity,
                "lead_time": lead,
                "synced_at": timezone.now(),
            },
        )

    # --- Услуги -----------------------------------------------------------

    def _create_services(self) -> int:
        categories = {}
        for order, (slug, name) in enumerate(data.SERVICE_CATEGORIES, start=1):
            category, _ = ServiceCategory.objects.update_or_create(
                slug=slug, defaults={"name": name, "sort_order": order * 10}
            )
            categories[slug] = category

        for order, row in enumerate(data.SERVICES, start=1):
            slug, name, category_slug, price, note, lead_time, on_site = row
            Service.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "category": categories[category_slug],
                    "short_description": f"{name} в сервисном центре филиала в Хабаровске.",
                    "description": (
                        f"{name}. Работы выполняет сервисная служба хабаровского филиала: "
                        f"обученные инженеры, оригинальные запасные части, гарантия на "
                        f"выполненные работы шесть месяцев."
                    ),
                    "price_from": Decimal(price) if price else None,
                    "price_note": note,
                    "lead_time": lead_time,
                    "is_on_site": on_site,
                    "is_available": True,
                    "is_published": True,
                    "published_at": timezone.now(),
                    "sort_order": order * 10,
                    "seo_title": f"{name} в Хабаровске — цена и сроки",
                    "seo_description": f"{name}: стоимость, сроки выполнения, выезд на объект.",
                },
            )
        self._say(f"Создано услуг: {len(data.SERVICES)}.")
        return len(data.SERVICES)

    # --- Контент ----------------------------------------------------------

    def _create_content(self, branch) -> int:
        settings_obj = SiteSettings.load()
        settings_obj.main_phone = "+7 (4212) 45-67-00"
        settings_obj.main_email = "khv@modernmachinery.ru"
        settings_obj.address = "Хабаровск, ул. Промышленная, 20"
        settings_obj.work_hours = "Пн–Сб 9:00–18:00"
        settings_obj.metrika_id = "29739990"
        settings_obj.socials = {
            "telegram": "https://t.me/modernmachinery_khv",
            "whatsapp": "https://wa.me/79147710542",
        }
        settings_obj.footer_text = (
            "Официальный дистрибьютор Komatsu, BOMAG, Manitou, Denyo на Дальнем Востоке."
        )
        settings_obj.save()

        pages = [
            (
                "o-kompanii-filial",
                "О филиале в Хабаровске",
                "Филиал «Модерн Машинери Фар Ист» работает в Хабаровске и обслуживает "
                "предприятия Хабаровского края, Еврейской автономной области и портов "
                "Ванино и Советская Гавань.",
            ),
            (
                "politika-konfidencialnosti",
                "Политика конфиденциальности",
                "Настоящая политика определяет порядок обработки персональных данных "
                "пользователей сайта в соответствии с Федеральным законом № 152-ФЗ "
                "«О персональных данных».",
            ),
        ]
        for slug, title, body in pages:
            page = Page.objects.filter(slug=slug).first()
            if page is None:
                page = Page.objects.add_root(
                    {
                        "slug": slug,
                        "title": title,
                        "body": body,
                        "is_published": True,
                        "published_at": timezone.now(),
                        "url_path": f"/{slug}/",
                    }
                )
            else:
                page.title = title
                page.body = body
                page.is_published = True
                page.save()

        privacy = Page.objects.filter(slug="politika-konfidencialnosti").first()
        if privacy:
            settings_obj.privacy_page = privacy
            settings_obj.save()

        menu_items = [
            ("header", "Техника", "/"),
            ("header", "Запчасти", "/zapchasti/"),
            ("header", "Сервисные услуги", "/uslugi/"),
            ("header", "О компании", "/o-kompanii/"),
            ("footer", "Новости", "/novosti/"),
            ("footer", "Вакансии", "/vakansii/"),
            ("footer", "Калькулятор стоимости владения", "/kalkulyator/"),
        ]
        for location, title, url in menu_items:
            if not MenuItem.objects.filter(location=location, title=title).exists():
                MenuItem.objects.add_root(
                    {"location": location, "title": title, "url": url, "is_visible": True}
                )

        category, _ = NewsCategory.objects.get_or_create(
            slug="novosti-filiala", defaults={"name": "Новости филиала"}
        )
        for index, (title, excerpt) in enumerate(data.NEWS):
            post, _ = NewsPost.objects.update_or_create(
                slug=slugify(slugify_ru(title))[:180],
                defaults={
                    "title": title,
                    "excerpt": excerpt,
                    "body": excerpt + "\n\nПодробности уточняйте у менеджеров филиала.",
                    "is_published": True,
                    "published_at": timezone.now() - timezone.timedelta(days=index * 9 + 2),
                },
            )
            post.categories.add(category)

        for title, dept_code, description, requirements, salary in data.VACANCIES:
            Vacancy.objects.update_or_create(
                slug=slugify(slugify_ru(title))[:180],
                defaults={
                    "title": title,
                    "branch": branch,
                    "department": Department.objects.filter(code=dept_code).first(),
                    "description": description,
                    "requirements": requirements,
                    "salary_note": salary,
                    "is_published": True,
                    "published_at": timezone.now(),
                },
            )

        ConsentVersion.objects.update_or_create(
            code="lead-form",
            version="1.0",
            defaults={
                "text": (
                    "Отправляя форму, я даю согласие на обработку персональных данных "
                    "в соответствии с Федеральным законом № 152-ФЗ и политикой "
                    "конфиденциальности сайта."
                ),
                "published_at": timezone.now(),
                "is_active": True,
            },
        )
        self._say("Контент, меню и согласие на обработку ПДн созданы.")
        return len(data.NEWS) + len(data.VACANCIES) + len(pages)

    # --- Маршрутизация заявок --------------------------------------------

    def _create_landings(self) -> int:
        """Заводит посадочные подборки под геозапросы.

        Подборка вида «Экскаваторы Komatsu в Хабаровске» — это отдельная
        индексируемая страница с собственным заголовком и текстом, а не набор
        параметров в адресе. Именно на такие запросы и рассчитан сайт филиала.
        """
        from apps.catalog.models import CatalogLanding

        for order, row in enumerate(data.CATALOG_LANDINGS, start=1):
            slug, title, brand_slug, type_slug, intro = row
            CatalogLanding.objects.update_or_create(
                slug=slug,
                defaults={
                    "title": title,
                    "intro": intro,
                    "brand": Brand.objects.filter(slug=brand_slug).first() if brand_slug else None,
                    "machine_type": MachineType.objects.filter(slug=type_slug).first()
                    if type_slug
                    else None,
                    "is_published": True,
                    "published_at": timezone.now(),
                    "is_featured": True,
                    "sort_order": order * 10,
                    "seo_title": f"{title} — купить, цены и характеристики",
                    "seo_description": intro[:160],
                    "seo_h1": title,
                },
            )
        self._say(f"Создано подборок каталога: {len(data.CATALOG_LANDINGS)}.")
        return len(data.CATALOG_LANDINGS)

    def _create_lead_rules(self) -> None:
        """Правила маршрутизации: заявка должна попасть в свой отдел.

        Порядок приоритетов задан так, что специфичное правило по складской
        технике выигрывает у общего правила по запросу цены.
        """
        emails = getattr(self, "_department_emails", {})
        rules = [
            (
                "Складская техника — отдел погрузочного оборудования",
                "",
                "vilochnyy-pogruzchik",
                "skladskoe-oborudovanie",
                10,
            ),
            (
                "Телескопические погрузчики — отдел погрузочного оборудования",
                "",
                "teleskopicheskiy-pogruzchik",
                "skladskoe-oborudovanie",
                10,
            ),
            ("Запросы запчастей", "parts", None, "zapchasti", 20),
            ("Заявки в сервис", "service", None, "servis", 20),
            ("Запрос цены на технику", "price", None, "prodazhi-tehniki", 50),
            ("Подбор техники", "selection", None, "prodazhi-tehniki", 50),
            ("Обратный звонок", "callback", None, "prodazhi-tehniki", 60),
            ("Калькулятор стоимости владения", "tco", None, "prodazhi-tehniki", 60),
            ("Отклик на вакансию", "vacancy", None, "uchebnyy-centr", 60),
        ]
        for name, lead_type, type_slug, dept_code, priority in rules:
            department = Department.objects.get(code=dept_code)
            shape = {
                "lead_type": lead_type,
                "machine_type": MachineType.objects.filter(slug=type_slug).first()
                if type_slug
                else None,
                "department": department,
                "priority": priority,
                "is_active": True,
            }
            # Список адресов заполняется только при создании правила. Менеджер
            # правит его в админке под реальные ящики филиала, и повторный
            # запуск наполнения не должен затирать эту настройку —
            # демонстрационные адреса вернулись бы поверх рабочих.
            LeadRoutingRule.objects.update_or_create(
                name=name,
                defaults=shape,
                create_defaults={
                    **shape,
                    "emails": [emails.get(dept_code, "office@modernmachinery.ru")],
                },
            )
