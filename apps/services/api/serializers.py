"""Сериализаторы модуля услуг."""

from rest_framework import serializers

from apps.services.models import Service, ServiceCategory


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ["id", "slug", "name", "icon"]


class ServiceSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.SlugField(source="category.slug", read_only=True)
    display_price = serializers.CharField(read_only=True)
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Service
        fields = [
            "id",
            "slug",
            "name",
            "category",
            "category_slug",
            "short_description",
            "description",
            "price_from",
            "price_note",
            "display_price",
            "is_on_site",
            "is_available",
            "lead_time",
            "url",
        ]
