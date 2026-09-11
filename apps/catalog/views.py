"""Страницы каталога техники.

Фильтры живут в query-string, а не в сессии: ссылку с подобранными параметрами
должно быть можно отправить коллеге, и она же должна индексироваться. HTMX
подменяет только список результатов, поэтому адрес страницы остаётся честным.
"""

from dataclasses import replace

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.views.generic import DetailView, TemplateView, View

from apps.leads.forms import MachineLeadForm
from apps.specs.models import SpecKey

from .models import CatalogLanding, Machine
from .services.facets import annotate_selection, get_facets
from .services.filters import apply_filters, parse_filters
from .throttling import check_search_throttle


class MachineListView(View):
    """Каталог техники с фасетными фильтрами.

    Запрос HTMX обслуживается тем же кодом, но отдаёт только фрагмент со
    списком: дублировать логику фильтрации ради частичного обновления нельзя,
    иначе выдача страницы и выдача фрагмента разойдутся.
    """

    template_name = "catalog/machine_list.html"
    partial_template_name = "catalog/partials/machine_grid.html"
    landing = None

    def get(self, request, **kwargs):
        spec_keys = list(SpecKey.objects.filter(is_filterable=True).select_related("group"))
        filters = self.get_filters(request, spec_keys)
        queryset = apply_filters(Machine.objects.visible().with_listing_relations(), filters)

        paginator = Paginator(queryset, settings.CATALOG_PAGE_SIZE)
        page = paginator.get_page(request.GET.get("page"))

        context = {
            "page_obj": page,
            "machines": page.object_list,
            "facets": annotate_selection(get_facets(filters), filters),
            "filters": filters,
            "total": paginator.count,
            "querystring": self._querystring_without_page(request),
            "landing": self.landing,
            "landings": self.get_landings(),
            **self.get_indexing_context(request, filters),
        }
        if request.headers.get("HX-Request"):
            return render(request, self.partial_template_name, context)
        return render(request, self.template_name, context)

    def get_filters(self, request, spec_keys):
        return parse_filters(request.GET, spec_keys)

    def get_landings(self):
        """Подборки для внутренней перелинковки под списком техники."""
        return CatalogLanding.objects.filter(is_published=True, is_featured=True).order_by(
            "sort_order", "title"
        )[:12]

    def get_indexing_context(self, request, filters) -> dict:
        """Определяет канонический адрес и правило индексации.

        Сочетаний фильтров тысячи, и каждое даёт свой адрес. Пускать их все в
        индекс — засорить выдачу почти одинаковыми страницами и размыть вес
        каталога. Поэтому индексируются только чистый каталог и подборки с
        собственными текстами, а отфильтрованные варианты ссылаются на них
        каноническим адресом.
        """
        return {
            "canonical_url": request.build_absolute_uri(request.path),
            "is_indexable": filters.active_count == 0 and not filters.query,
        }

    @staticmethod
    def _querystring_without_page(request) -> str:
        """Строка параметров без номера страницы — для ссылок пагинации."""
        params = request.GET.copy()
        params.pop("page", None)
        return params.urlencode()


class CatalogLandingView(MachineListView):
    """Посадочная страница каталога под конкретный запрос.

    Переиспользует всю механику каталога и лишь подмешивает условия подборки:
    фильтры, фасеты и пагинация обязаны вести себя одинаково, иначе на
    посадочной странице появится собственный набор ошибок.
    """

    template_name = "catalog/landing.html"

    def get(self, request, slug: str, **kwargs):
        self.landing = get_object_or_404(
            CatalogLanding.objects.select_related("brand", "machine_type", "category"),
            slug=slug,
            is_published=True,
        )
        return super().get(request, **kwargs)

    def get_filters(self, request, spec_keys):
        """Условия подборки жёстко добавляются к тем, что выбрал посетитель."""
        filters = super().get_filters(request, spec_keys)
        landing = self.landing
        return replace(
            filters,
            brands=[landing.brand.slug] if landing.brand_id else filters.brands,
            machine_types=(
                [landing.machine_type.slug] if landing.machine_type_id else filters.machine_types
            ),
            categories=[landing.category.slug] if landing.category_id else filters.categories,
        )

    def get_landings(self):
        return (
            CatalogLanding.objects.filter(is_published=True, is_featured=True)
            .exclude(pk=self.landing.pk)
            .order_by("sort_order", "title")[:12]
        )

    def get_indexing_context(self, request, filters) -> dict:
        """Подборка индексируется, пока к ней не добавили сторонних условий."""
        extra = filters.active_count - self._landing_conditions()
        return {
            "canonical_url": request.build_absolute_uri(self.landing.get_absolute_url()),
            "is_indexable": extra <= 0 and not filters.query,
        }

    def _landing_conditions(self) -> int:
        return sum(
            1
            for value in (
                self.landing.brand_id,
                self.landing.machine_type_id,
                self.landing.category_id,
            )
            if value
        )


class MachineDetailView(DetailView):
    """Карточка модели техники."""

    template_name = "catalog/machine_detail.html"
    context_object_name = "machine"

    def get_queryset(self):
        return Machine.objects.visible().with_detail_relations()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        machine = self.object

        # Характеристики группируются для таба «Характеристики»: плоский список
        # на полсотни строк читать невозможно.
        groups: dict[str, list] = {}
        for spec in machine.specs.all():
            groups.setdefault(spec.spec_key.group.name, []).append(spec)

        context["spec_groups"] = groups
        context["lead_form"] = MachineLeadForm(initial={"machine": machine.pk})
        context["related_parts"] = machine.parts.select_related("part", "part__brand").filter(
            part__is_active=True, part__is_published=True
        )[:6]
        context["similar_machines"] = (
            Machine.objects.visible()
            .with_listing_relations()
            .filter(machine_type=machine.machine_type)
            .exclude(pk=machine.pk)[:4]
        )
        return context


class MachineCompareView(TemplateView):
    """Сравнение моделей техники.

    То, ради чего вообще нормализуются характеристики: снабженец выбирает
    несколько машин и видит их параметры бок о бок. На старом сайте такое
    невозможно в принципе — там значения лежат строками в вёрстке.

    Модели передаются в адресе, а не в сессии: подобранное сравнение нужно
    уметь отправить коллеге или главному механику.
    """

    template_name = "catalog/machine_compare.html"
    max_items = 4

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        slugs = [slug for slug in self.request.GET.getlist("m") if slug][: self.max_items]

        machines = list(Machine.objects.visible().with_detail_relations().filter(slug__in=slugs))
        # Порядок в таблице — тот, в котором посетитель добавлял машины,
        # а не тот, в котором их вернула база.
        order = {slug: index for index, slug in enumerate(slugs)}
        machines.sort(key=lambda item: order.get(item.slug, len(order)))

        context["machines"] = machines
        context["max_items"] = self.max_items
        context["spec_groups"] = self._build_rows(machines)
        return context

    @staticmethod
    def _build_rows(machines: list[Machine]) -> list[dict]:
        """Собирает строки таблицы, помечая различающиеся параметры.

        Совпадающие значения тоже показываются: снабженцу важно видеть, что
        параметр одинаков, а не гадать, почему строка исчезла. Но подсвечиваются
        именно различия — ради них сравнение и открывают.
        """
        if not machines:
            return []

        values: dict[int, dict[str, str]] = {}
        keys: dict[str, object] = {}
        for machine in machines:
            for spec in machine.specs.all():
                if not spec.spec_key.is_comparable:
                    continue
                keys.setdefault(spec.spec_key.code, spec.spec_key)
                values.setdefault(machine.pk, {})[spec.spec_key.code] = spec.display_value

        groups: dict[str, list] = {}
        for code, key in sorted(
            keys.items(), key=lambda item: (item[1].group.sort_order, item[1].sort_order)
        ):
            row_values = [values.get(machine.pk, {}).get(code, "—") for machine in machines]
            filled = [value for value in row_values if value != "—"]
            groups.setdefault(key.group.name, []).append(
                {
                    "key": key,
                    "values": row_values,
                    "is_different": len(set(filled)) > 1,
                }
            )

        return [{"name": name, "rows": rows} for name, rows in groups.items()]


def machine_search_suggest(request):
    """Автодополнение поиска для HTMX.

    Отдаёт короткий список совпадений: это подсказка, а не выдача. Частота
    ограничена — за каждым нажатием клавиши стоит полнотекстовый запрос.
    """
    if not check_search_throttle(request):
        # Молчаливый отказ вместо ошибки: подсказка не критична для сценария,
        # а сообщение об ошибке под полем ввода только мешало бы.
        return render(request, "catalog/partials/search_suggest.html", {"suggestions": []})

    query = (request.GET.get("q") or "").strip()
    machines = []
    if len(query) >= 2:
        machines = list(Machine.objects.visible().search(query).select_related("brand")[:8])
    return render(request, "catalog/partials/search_suggest.html", {"suggestions": machines})
