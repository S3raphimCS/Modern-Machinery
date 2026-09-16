"""Контентные страницы, приём заявок и калькулятор стоимости владения."""

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from apps.company.models import Branch
from apps.leads.forms import (
    CallbackForm,
    LeadForm,
    MachineLeadForm,
    PartLeadForm,
    ServiceLeadForm,
    TcoForm,
)
from apps.leads.models import Lead
from apps.leads.services.creation import create_lead
from apps.leads.services.tco import calculate_tco
from apps.leads.throttling import check_lead_throttles

from .models import NewsPost, Page, Review, ReviewSource, Vacancy

# Тип заявки задаётся страницей, а не пользователем: иначе форму можно
# использовать для подмены маршрутизации.
LEAD_FORMS = {
    Lead.Type.PRICE: MachineLeadForm,
    Lead.Type.SELECTION: MachineLeadForm,
    Lead.Type.PARTS: PartLeadForm,
    Lead.Type.SERVICE: ServiceLeadForm,
    Lead.Type.CALLBACK: CallbackForm,
    Lead.Type.VACANCY: LeadForm,
}


class AboutView(DetailView):
    """Страница «О компании» с контактами филиала."""

    template_name = "content/about.html"
    context_object_name = "branch"

    def get_object(self, queryset=None):
        branch = (
            Branch.objects.filter(is_published=True)
            .prefetch_related("contacts", "employees__contacts", "employees__department")
            .first()
        )
        if branch is None:
            raise Http404("Филиал не заполнен")
        return branch


class NewsListView(ListView):
    template_name = "content/news_list.html"
    context_object_name = "posts"
    paginate_by = 12

    def get_queryset(self):
        return NewsPost.objects.visible().prefetch_related("categories")


class NewsDetailView(DetailView):
    template_name = "content/news_detail.html"
    context_object_name = "post"

    def get_queryset(self):
        return NewsPost.objects.visible().prefetch_related("categories", "machines__brand")


class ReviewListView(ListView):
    """Страница отзывов.

    Микроразметки здесь нет намеренно: отзыв организации о самой себе не даёт
    звёзд в выдаче по правилам поисковиков, а перенос чужих рейтингов в свою
    разметку прямо запрещён. Разметка ставится только на карточке техники,
    где отзыв относится к товару.
    """

    template_name = "content/review_list.html"
    context_object_name = "reviews"
    paginate_by = 20

    def get_queryset(self):
        return Review.objects.visible().select_related("machine", "service")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sources"] = ReviewSource.objects.filter(is_active=True)
        return context


class VacancyListView(ListView):
    template_name = "content/vacancy_list.html"
    context_object_name = "vacancies"

    def get_queryset(self):
        return Vacancy.objects.visible().select_related("branch", "department")


class VacancyDetailView(DetailView):
    template_name = "content/vacancy_detail.html"
    context_object_name = "vacancy"

    def get_queryset(self):
        return Vacancy.objects.visible().select_related("branch", "department")


class PageDetailView(DetailView):
    """Произвольная страница, найденная по полному пути."""

    context_object_name = "page"

    def get_object(self, queryset=None):
        url_path = "/" + self.kwargs["path"].strip("/") + "/"
        return get_object_or_404(
            Page.objects.filter(is_published=True).prefetch_related("blocks"),
            url_path=url_path,
        )

    def get_template_names(self) -> list[str]:
        # Шаблон задаётся в админке, но подставить произвольный путь нельзя:
        # значение проверяется на принадлежность каталогу страниц.
        template = self.object.template or "pages/default.html"
        if not template.startswith("pages/") or ".." in template:
            template = "pages/default.html"
        return [template, "pages/default.html"]


@require_POST
def lead_create(request, lead_type: str):
    """Принимает заявку из HTML-формы.

    Дросселирование здесь то же самое, что и в API: иначе форма стала бы
    обходным путём для лимита, поставленного на ручку.
    """
    form_class = LEAD_FORMS.get(lead_type)
    if form_class is None:
        raise Http404("Неизвестный тип заявки")

    if not check_lead_throttles(request):
        context = {"error": "Слишком много заявок с вашего адреса. Попробуйте позже."}
        return render(request, "leads/partials/form_error.html", context, status=429)

    form = form_class(request.POST, request.FILES)
    if not form.is_valid():
        return render(
            request,
            "leads/partials/form.html",
            {"lead_form": form, "lead_type": lead_type},
            status=400,
        )

    data = form.to_lead_data()
    data["type"] = lead_type
    lead, created = create_lead(
        data=data,
        request=request,
        consent_given=form.cleaned_data["consent"],
        files=form.cleaned_data.get("attachments"),
    )
    return render(request, "leads/partials/form_success.html", {"lead": lead, "created": created})


def tco_calculator(request):
    """Калькулятор стоимости владения.

    GET отдаёт форму, POST считает результат и сохраняет обращение как заявку
    типа «калькулятор» — это лид-магнит, а не просто виджет.
    """
    if request.method != "POST":
        return render(request, "content/tco.html", {"form": TcoForm()})

    form = TcoForm(request.POST)
    if not form.is_valid():
        return render(request, "content/partials/tco_result.html", {"form": form}, status=400)

    result = calculate_tco(**form.to_kwargs())
    context = {"form": form, "result": result}

    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    if name and phone and check_lead_throttles(request):
        # Контакты в калькуляторе необязательны: расчёт показывается всем,
        # заявка создаётся только если посетитель сам оставил телефон.
        create_lead(
            data={
                "type": Lead.Type.TCO,
                "name": name,
                "phone": phone,
                "payload": {"input": form.to_kwargs_serializable(), "result": result.as_dict()},
            },
            request=request,
        )
        context["lead_saved"] = True

    if request.headers.get("HX-Request"):
        return render(request, "content/partials/tco_result.html", context)
    return render(request, "content/tco.html", context)


def privacy_policy(request) -> HttpResponse:
    """Политика конфиденциальности — обязательная страница при сборе ПДн."""
    page = Page.objects.filter(is_published=True, slug="politika-konfidencialnosti").first()
    return render(request, "content/privacy.html", {"page": page})


def lead_form_modal(request) -> HttpResponse:
    """Отдаёт разметку модального окна заявки для HTMX.

    Тип приходит из query-строки, поэтому неизвестное значение приводится к
    типу по умолчанию: иначе шаблон не смог бы построить адрес отправки формы
    и страница падала бы вместо показа модалки.
    """
    lead_type = request.GET.get("type", Lead.Type.PRICE)
    if lead_type not in LEAD_FORMS:
        lead_type = Lead.Type.PRICE
    return render(
        request,
        "leads/partials/modal.html",
        {"lead_form": LEAD_FORMS[lead_type](), "lead_type": lead_type},
    )
