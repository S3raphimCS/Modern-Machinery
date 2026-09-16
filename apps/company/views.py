"""Страницы модуля компании."""

from django.views.generic import ListView

from .models import Branch, DeliveryOption


class DeliveryView(ListView):
    """Раздел доставки.

    Для Дальнего Востока расстояния таковы, что способ доставки обсуждают
    раньше цены, поэтому раздел отдельный, а не строчка в описании.
    """

    template_name = "company/delivery.html"
    context_object_name = "options"

    def get_queryset(self):
        return DeliveryOption.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["branch"] = Branch.objects.filter(is_published=True).first()
        return context
