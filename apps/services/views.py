"""Страницы модуля услуг."""

from django.views.generic import DetailView, ListView

from apps.leads.forms import ServiceLeadForm

from .models import Service, ServiceCategory


class ServiceListView(ListView):
    """Каталог сервисных услуг.

    Для филиала это самостоятельная посадочная страница под геозапросы вида
    «ремонт спецтехники Хабаровск», а не приложение к каталогу техники.
    """

    template_name = "services/service_list.html"
    context_object_name = "services"

    def get_queryset(self):
        queryset = Service.objects.visible().select_related("category")
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category__slug=category)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = ServiceCategory.objects.all()
        context["active_category"] = self.request.GET.get("category")
        context["lead_form"] = ServiceLeadForm()
        return context


class ServiceDetailView(DetailView):
    """Страница услуги."""

    template_name = "services/service_detail.html"
    context_object_name = "service"

    def get_queryset(self):
        return (
            Service.objects.visible()
            .select_related("category")
            .prefetch_related("machine_types", "brands")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["lead_form"] = ServiceLeadForm(initial={"service": self.object.pk})
        return context
