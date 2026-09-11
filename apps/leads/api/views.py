"""Эндпоинты заявок и калькулятора стоимости владения."""

from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.leads.services.creation import create_lead
from apps.leads.services.tco import calculate_tco
from apps.leads.throttling import LeadBurstRateThrottle, LeadRateThrottle

from .serializers import LeadCreateSerializer, LeadResultSerializer, TcoCalculateSerializer


class LeadViewSet(viewsets.ViewSet):
    """Приём заявок с сайта.

    Единственная публичная ручка записи, поэтому на ней стоят обе корзины
    дросселирования — часовая и минутная. Чтение заявок наружу не выведено
    намеренно: это персональные данные.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LeadBurstRateThrottle, LeadRateThrottle]
    serializer_class = LeadCreateSerializer

    @extend_schema(
        request=LeadCreateSerializer,
        responses={201: LeadResultSerializer, 429: None},
        description=(
            "Создаёт заявку. Повторная отправка того же содержимого в пределах окна "
            "дедупликации возвращает уже созданную заявку с признаком created=false."
        ),
    )
    def create(self, request):
        serializer = LeadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead, created = create_lead(
            data=serializer.to_lead_data(),
            request=request,
            consent_given=serializer.validated_data["consent"],
        )
        payload = LeadResultSerializer(lead).data
        payload["created"] = created
        return Response(payload, status=status.HTTP_201_CREATED)


class TcoViewSet(viewsets.ViewSet):
    """Калькулятор стоимости владения техникой."""

    permission_classes = [AllowAny]
    serializer_class = TcoCalculateSerializer

    @extend_schema(
        request=TcoCalculateSerializer,
        responses={200: dict},
        description="Считает годовую стоимость владения и стоимость машино-часа.",
    )
    @action(detail=False, methods=["post"])
    def calculate(self, request):
        serializer = TcoCalculateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = calculate_tco(**serializer.validated_data)
        return Response(result.as_dict())
