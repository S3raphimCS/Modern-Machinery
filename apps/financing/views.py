"""Страница лизинга и кредита."""

from django.shortcuts import render

from apps.financing.forms import LeasingCalculatorForm
from apps.financing.models import LeasingPartner, LeasingTerms
from apps.financing.services.leasing import calculate_leasing
from apps.leads.models import Lead
from apps.leads.services.creation import create_lead
from apps.leads.throttling import check_lead_throttles


def leasing(request):
    """Раздел финансирования с калькулятором платежа.

    GET отдаёт страницу с условиями и партнёрами, POST считает платёж.
    Расчёт показывается всем; заявка создаётся, только если посетитель сам
    оставил контакты — как и в калькуляторе стоимости владения.

    Пересчёт по ходу ввода помечен `action=calc`: он приходит на каждое
    изменение поля, и заявку по нему создавать нельзя — человек ещё набирает
    телефон, а не отправляет его.
    """
    terms = LeasingTerms.load()
    partners = LeasingPartner.objects.filter(is_active=True)

    if request.method != "POST":
        context = {"form": LeasingCalculatorForm(), "terms": terms, "partners": partners}
        return render(request, "financing/leasing.html", context)

    live_recalculation = request.POST.get("action") == "calc"

    form = LeasingCalculatorForm(request.POST)
    if not form.is_valid():
        context = {"form": form, "terms": terms, "partners": partners}
        # Код 200, а не 400: htmx по умолчанию не подставляет ответы с ошибкой,
        # и сообщение о неверном значении просто не дошло бы до страницы.
        return render(request, "financing/partials/result.html", context)

    result = calculate_leasing(**form.to_kwargs())
    context = {"form": form, "terms": terms, "partners": partners, "result": result}

    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    if not live_recalculation and name and phone and check_lead_throttles(request):
        lead, created = create_lead(
            data={
                "type": Lead.Type.LEASING,
                "name": name,
                "phone": phone,
                # Расчёт сохраняется целиком: менеджер видит, из каких чисел
                # исходил клиент, и продолжает разговор с них же.
                "payload": {
                    "input": form.to_kwargs_serializable(),
                    "result": result.as_dict(),
                },
            },
            request=request,
        )
        # Блок подтверждения показывается по наличию заявки, а текст и цель —
        # по признаку создания: при склейке повтора новой записи нет, но
        # молчать в ответ нельзя — это выглядит как сломанная кнопка.
        context["lead"] = lead
        context["created"] = created

    if request.headers.get("HX-Request"):
        return render(request, "financing/partials/result.html", context)
    return render(request, "financing/leasing.html", context)
