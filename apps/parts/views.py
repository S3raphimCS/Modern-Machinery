"""Страницы каталога запчастей."""

from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.generic import DetailView, View

from apps.leads.forms import PartLeadForm

from .models import Part, PartCategory


class PartListView(View):
    """Каталог запчастей с поиском по артикулу.

    В макете десктоп показывает таблицу, мобильный — карточки. Данные для обоих
    одинаковые, разделение живёт в шаблоне.
    """

    template_name = "parts/part_list.html"
    partial_template_name = "parts/partials/part_results.html"
    page_size = 20

    def get(self, request):
        queryset = (
            Part.objects.visible().select_related("brand", "category").prefetch_related("stocks")
        )
        query = (request.GET.get("q") or "").strip()
        category_slug = request.GET.get("category")

        if query:
            queryset = queryset.search(query)
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        paginator = Paginator(queryset, self.page_size)
        page = paginator.get_page(request.GET.get("page"))

        context = {
            "page_obj": page,
            "parts": page.object_list,
            "categories": PartCategory.objects.filter(is_active=True).order_by("path"),
            "active_category": category_slug,
            "query": query,
            "total": paginator.count,
        }
        if request.headers.get("HX-Request"):
            return render(request, self.partial_template_name, context)
        return render(request, self.template_name, context)


class PartDetailView(DetailView):
    """Карточка запчасти."""

    template_name = "parts/part_detail.html"
    context_object_name = "part"

    def get_queryset(self):
        return (
            Part.objects.visible()
            .select_related("brand", "category")
            .prefetch_related("stocks__branch", "applicability__machine__brand", "analogs__analog")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["lead_form"] = PartLeadForm(initial={"part": self.object.pk})
        return context
