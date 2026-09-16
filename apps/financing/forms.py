"""Формы раздела финансирования."""

from django import forms

from apps.financing.models import LeasingTerms


class LeasingCalculatorForm(forms.Form):
    """Калькулятор лизингового платежа.

    Границы полей берутся из условий в админке: менеджер меняет «аванс от
    10%» — и калькулятор перестаёт принимать меньшие значения, без правки
    кода.
    """

    price = forms.DecimalField(
        label="Стоимость техники",
        min_value=1,
        max_digits=14,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                "class": "mm-input",
                "placeholder": "18 000 000",
                "step": "any",
                "inputmode": "numeric",
            }
        ),
    )
    advance_percent = forms.IntegerField(
        label="Аванс",
        widget=forms.NumberInput(attrs={"class": "mm-input", "step": "1", "inputmode": "numeric"}),
    )
    months = forms.IntegerField(
        label="Срок",
        widget=forms.NumberInput(attrs={"class": "mm-input", "step": "1", "inputmode": "numeric"}),
    )
    markup_percent = forms.DecimalField(
        label="Удорожание в год",
        min_value=0,
        max_value=50,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={"class": "mm-input", "step": "any", "inputmode": "decimal"}
        ),
    )

    UNITS = {
        "price": "₽",
        "advance_percent": "%",
        "months": "мес",
        "markup_percent": "%",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        terms = LeasingTerms.load()
        self.terms = terms

        advance = self.fields["advance_percent"]
        advance.min_value = terms.min_advance_percent
        advance.max_value = terms.max_advance_percent
        advance.validators = forms.IntegerField(
            min_value=terms.min_advance_percent, max_value=terms.max_advance_percent
        ).validators
        advance.initial = terms.default_advance_percent
        advance.widget.attrs.update(
            {"min": terms.min_advance_percent, "max": terms.max_advance_percent}
        )

        months = self.fields["months"]
        months.validators = forms.IntegerField(
            min_value=terms.min_months, max_value=terms.max_months
        ).validators
        months.initial = terms.default_months
        months.widget.attrs.update({"min": terms.min_months, "max": terms.max_months})

        self.fields["markup_percent"].initial = terms.default_markup_percent

    def fields_with_units(self):
        """Поля вместе с единицами измерения — для вывода в шаблоне."""
        for name, unit in self.UNITS.items():
            yield {"field": self[name], "unit": unit}

    def to_kwargs(self) -> dict:
        data = self.cleaned_data
        return {
            "price": data["price"],
            "advance_percent": data["advance_percent"],
            "months": data["months"],
            "markup_percent": data["markup_percent"],
        }

    def to_kwargs_serializable(self) -> dict:
        """То же, но пригодное для записи в JSON-поле заявки."""
        return {key: float(value) for key, value in self.to_kwargs().items()}
