"""Сериализаторы заявок.

Заявка — единственная сущность, которую публичный API создаёт, поэтому здесь же
живут проверки, аналогичные HTML-форме: ловушка, время заполнения и обязательный
способ связи.
"""

from __future__ import annotations

import time

from django.conf import settings
from django.core import signing
from rest_framework import serializers

from apps.catalog.models import Machine
from apps.leads.forms import FORM_TS_SALT
from apps.leads.models import Lead
from apps.parts.models import Part
from apps.services.models import Service


class LeadCreateSerializer(serializers.Serializer):
    """Входные данные для создания заявки."""

    type = serializers.ChoiceField(choices=Lead.Type.choices)
    name = serializers.CharField(max_length=160)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    company = serializers.CharField(max_length=200, required=False, allow_blank=True)
    inn = serializers.CharField(max_length=12, required=False, allow_blank=True)
    message = serializers.CharField(required=False, allow_blank=True)
    consent = serializers.BooleanField()

    machine = serializers.SlugRelatedField(
        slug_field="slug", queryset=Machine.objects.visible(), required=False, allow_null=True
    )
    part = serializers.PrimaryKeyRelatedField(
        queryset=Part.objects.visible(), required=False, allow_null=True
    )
    service = serializers.SlugRelatedField(
        slug_field="slug", queryset=Service.objects.visible(), required=False, allow_null=True
    )

    payload = serializers.JSONField(required=False)
    # Те же две защиты, что и в HTML-форме: иначе API стал бы обходным путём.
    website = serializers.CharField(required=False, allow_blank=True)
    form_ts = serializers.CharField(required=False, allow_blank=True)

    def validate_consent(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError(
                "Без согласия на обработку персональных данных заявка не принимается."
            )
        return value

    def validate_website(self, value: str) -> str:
        if value:
            raise serializers.ValidationError("Не удалось отправить заявку.")
        return ""

    def validate_form_ts(self, value: str) -> str:
        if not value:
            return ""
        try:
            started = signing.loads(value, salt=FORM_TS_SALT, max_age=60 * 60 * 6)
        except signing.BadSignature:
            raise serializers.ValidationError("Форма устарела, обновите страницу.") from None
        if time.time() - float(started) < settings.LEAD_MIN_FORM_SECONDS:
            raise serializers.ValidationError("Не удалось отправить заявку.")
        return value

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("phone") and not attrs.get("email"):
            raise serializers.ValidationError({"phone": "Укажите телефон или e-mail для связи."})
        return attrs

    def to_lead_data(self) -> dict:
        """Оставляет только поля модели, отбрасывая служебные."""
        data = dict(self.validated_data)
        for field in ("consent", "website", "form_ts"):
            data.pop(field, None)
        return data


class LeadResultSerializer(serializers.ModelSerializer):
    """Ответ на успешное создание заявки.

    Персональные данные обратно не отдаются: ответ подтверждает приём и не более.
    """

    created = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lead
        fields = ["id", "type", "status", "created_at", "created"]
        read_only_fields = fields


class TcoCalculateSerializer(serializers.Serializer):
    """Входные данные калькулятора стоимости владения."""

    hours_per_year = serializers.IntegerField(min_value=1, max_value=20000)
    fuel_consumption = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0)
    fuel_price = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0)
    maintenance_cost_year = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, default=0
    )
    machine_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0, required=False, default=0
    )
    lifetime_years = serializers.IntegerField(min_value=1, max_value=30, required=False, default=7)
    operator_cost_month = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, default=0
    )
