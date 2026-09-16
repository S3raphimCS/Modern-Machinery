"""Формы заявок с сайта.

Защита от ботов сделана без reCAPTCHA: в РФ она работает нестабильно, а на B2B-
аудитории капча заметно режет конверсию. Вместо неё три дешёвых приёма, которые
вместе отсекают почти весь автоматический трафик: скрытое поле-ловушка,
минимальное время заполнения и подписанная метка времени формы.
"""

from __future__ import annotations

import time

from django import forms
from django.conf import settings
from django.core import signing

from apps.catalog.models import Machine
from apps.leads.models import Lead
from apps.leads.validators import (
    ALLOWED_EXTENSIONS,
    MAX_FILES_PER_LEAD,
    LeadFileValidator,
)
from apps.parts.models import Part
from apps.services.models import Service

FORM_TS_SALT = "leads.form.timestamp"


class MultipleFileInput(forms.ClearableFileInput):
    """Поле выбора нескольких файлов.

    Начиная с Django 5.0 обычный виджет с `multiple` намеренно запрещён:
    он молча терял все файлы, кроме последнего. Пара «виджет + поле» ниже —
    рекомендованный способ обойтись без этой ловушки.
    """

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Файловое поле, возвращающее список файлов и проверяющее каждый."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, list | tuple):
            files = [single(item, initial) for item in data if item]
        else:
            files = [single(data, initial)] if data else []

        if len(files) > MAX_FILES_PER_LEAD:
            raise forms.ValidationError(f"Можно приложить не больше {MAX_FILES_PER_LEAD} файлов.")
        return files


class LeadForm(forms.Form):
    """Базовая форма заявки.

    Поля соответствуют модалке из макета: имя, телефон, комментарий. Остальное
    (тип заявки, привязка к технике) проставляется вьюшкой из контекста страницы.
    """

    name = forms.CharField(label="Ваше имя", max_length=160)
    phone = forms.CharField(label="Телефон", max_length=40, required=False)
    email = forms.EmailField(label="E-mail", required=False)
    company = forms.CharField(label="Компания", max_length=200, required=False)
    message = forms.CharField(label="Комментарий", widget=forms.Textarea, required=False)
    attachments = MultipleFileField(
        label="Прикрепить файлы",
        required=False,
        validators=[LeadFileValidator()],
        help_text=f"Спецификация, техническое задание или список артикулов. "
        f"До {MAX_FILES_PER_LEAD} файлов: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
    )
    consent = forms.BooleanField(label="Согласен на обработку персональных данных", required=True)

    # Ловушка: поле скрыто стилями, человек его не видит и не заполняет.
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    # Подписанная метка времени: подделать её, не зная SECRET_KEY, нельзя.
    form_ts = forms.CharField(required=False, widget=forms.HiddenInput)

    lead_type = Lead.Type.PRICE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["form_ts"].initial = signing.dumps(time.time(), salt=FORM_TS_SALT)

    def clean_website(self) -> str:
        """Заполненная ловушка означает бота."""
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Не удалось отправить заявку.")
        return ""

    def clean_form_ts(self) -> str:
        """Отсекает отправку быстрее, чем форму способен заполнить человек."""
        raw = self.cleaned_data.get("form_ts")
        if not raw:
            # Отсутствие метки не блокирует отправку: форма могла быть
            # отрисована до включения проверки или закеширована браузером.
            return ""
        try:
            started = signing.loads(raw, salt=FORM_TS_SALT, max_age=60 * 60 * 6)
        except signing.BadSignature:
            raise forms.ValidationError("Форма устарела, обновите страницу.") from None
        if time.time() - float(started) < settings.LEAD_MIN_FORM_SECONDS:
            raise forms.ValidationError("Не удалось отправить заявку.")
        return raw

    def clean(self) -> dict:
        cleaned = super().clean()
        # Заявка без единого способа связи бесполезна отделу продаж.
        if not cleaned.get("phone") and not cleaned.get("email"):
            raise forms.ValidationError("Укажите телефон или e-mail для связи.")
        return cleaned

    def to_lead_data(self) -> dict:
        """Готовит поля модели из очищенных данных формы."""
        data = {
            "type": self.lead_type,
            "name": self.cleaned_data["name"],
            "phone": self.cleaned_data.get("phone", ""),
            "email": self.cleaned_data.get("email", ""),
            "company": self.cleaned_data.get("company", ""),
            "message": self.cleaned_data.get("message", ""),
        }
        return data


class MachineLeadForm(LeadForm):
    """Заявка по конкретной модели техники."""

    machine = forms.ModelChoiceField(
        queryset=Machine.objects.visible(), required=False, widget=forms.HiddenInput
    )

    def to_lead_data(self) -> dict:
        data = super().to_lead_data()
        data["machine"] = self.cleaned_data.get("machine")
        return data


class PartLeadForm(LeadForm):
    """Запрос по запчасти."""

    lead_type = Lead.Type.PARTS

    part = forms.ModelChoiceField(
        queryset=Part.objects.visible(), required=False, widget=forms.HiddenInput
    )

    def to_lead_data(self) -> dict:
        data = super().to_lead_data()
        data["part"] = self.cleaned_data.get("part")
        return data


class ServiceLeadForm(LeadForm):
    """Заявка на сервисную услугу."""

    lead_type = Lead.Type.SERVICE

    service = forms.ModelChoiceField(
        queryset=Service.objects.visible(), required=False, widget=forms.HiddenInput
    )

    def to_lead_data(self) -> dict:
        data = super().to_lead_data()
        data["service"] = self.cleaned_data.get("service")
        return data


class CallbackForm(LeadForm):
    """Обратный звонок: короткая форма из подвала и модалки."""

    lead_type = Lead.Type.CALLBACK

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone"].required = True
        self.fields["email"].required = False


class TcoForm(forms.Form):
    """Калькулятор стоимости владения.

    Оформление полей задаётся здесь, а не в шаблоне: единица измерения и
    подсказка — часть описания поля, и держать их в вёрстке значит правкой
    шаблона незаметно менять смысл формы.
    """

    hours_per_year = forms.IntegerField(
        label="Наработка в год",
        min_value=1,
        max_value=20000,
        widget=forms.NumberInput(
            attrs={"class": "mm-input", "placeholder": "1800", "inputmode": "numeric"}
        ),
    )
    fuel_consumption = forms.DecimalField(
        label="Расход топлива",
        min_value=0,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={"class": "mm-input", "placeholder": "22", "step": "0.1", "inputmode": "decimal"}
        ),
    )
    fuel_price = forms.DecimalField(
        label="Цена топлива",
        min_value=0,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={"class": "mm-input", "placeholder": "65", "step": "0.5", "inputmode": "decimal"}
        ),
    )
    maintenance_cost_year = forms.DecimalField(
        label="Стоимость ТО в год",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "mm-input",
                "placeholder": "450 000",
                "step": "1000",
                "inputmode": "numeric",
            }
        ),
    )
    operator_cost_month = forms.DecimalField(
        label="Зарплата оператора в месяц",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "mm-input",
                "placeholder": "120 000",
                "step": "1000",
                "inputmode": "numeric",
            }
        ),
    )
    machine_price = forms.DecimalField(
        label="Стоимость машины",
        min_value=0,
        max_digits=14,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "mm-input",
                "placeholder": "18 000 000",
                "step": "100000",
                "inputmode": "numeric",
            }
        ),
    )
    lifetime_years = forms.IntegerField(
        label="Срок службы",
        min_value=1,
        max_value=30,
        required=False,
        initial=7,
        widget=forms.NumberInput(
            attrs={"class": "mm-input", "placeholder": "7", "inputmode": "numeric"}
        ),
    )

    # Единицы вынесены из подписей: в подписи они превращали короткое название
    # в строку вида «Наработка в год, моточасов» и ломали вёрстку на мобильном.
    UNITS = {
        "hours_per_year": "моточасов",
        "fuel_consumption": "л/ч",
        "fuel_price": "₽/л",
        "maintenance_cost_year": "₽",
        "operator_cost_month": "₽",
        "machine_price": "₽",
        "lifetime_years": "лет",
    }

    # Поля сгруппированы по смыслу: семь полей подряд читаются как анкета,
    # три блока по два-три — как понятная форма.
    GROUPS = [
        ("Эксплуатация", ["hours_per_year", "fuel_consumption", "fuel_price"]),
        ("Затраты", ["maintenance_cost_year", "operator_cost_month"]),
        ("Машина", ["machine_price", "lifetime_years"]),
    ]

    def grouped_fields(self):
        """Отдаёт поля блоками вместе с единицами измерения."""
        for title, names in self.GROUPS:
            yield {
                "title": title,
                "fields": [
                    {"field": self[name], "unit": self.UNITS.get(name, "")} for name in names
                ],
            }

    def to_kwargs_serializable(self) -> dict:
        """То же, что `to_kwargs`, но пригодное для записи в JSON-поле.

        Decimal не сериализуется в JSON, а входные данные расчёта сохраняются
        в заявке — по ним менеджер понимает, что именно считал посетитель.
        """
        return {key: float(value) for key, value in self.to_kwargs().items()}

    def to_kwargs(self) -> dict:
        """Приводит данные формы к аргументам расчёта."""
        data = self.cleaned_data
        return {
            "hours_per_year": data["hours_per_year"],
            "fuel_consumption": data["fuel_consumption"],
            "fuel_price": data["fuel_price"],
            "maintenance_cost_year": data.get("maintenance_cost_year") or 0,
            "machine_price": data.get("machine_price") or 0,
            "lifetime_years": data.get("lifetime_years") or 7,
            "operator_cost_month": data.get("operator_cost_month") or 0,
        }
