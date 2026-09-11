"""Сериализаторы каталога запчастей."""

from rest_framework import serializers

from apps.parts.models import Part, PartCategory, PartStock


class PartCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PartCategory
        fields = ["id", "slug", "name", "description"]


class PartStockSerializer(serializers.ModelSerializer):
    branch = serializers.CharField(source="branch.city", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PartStock
        # Количество наружу не отдаётся — только статус.
        fields = ["branch", "status", "status_display", "lead_time"]


class PartListSerializer(serializers.ModelSerializer):
    brand = serializers.CharField(source="brand.name", read_only=True)
    category = serializers.CharField(source="category.name", read_only=True)
    stock_status = serializers.CharField(read_only=True)

    class Meta:
        model = Part
        fields = [
            "id",
            "article",
            "name",
            "brand",
            "category",
            "is_original",
            "unit",
            "image",
            "stock_status",
        ]


class PartDetailSerializer(PartListSerializer):
    stocks = PartStockSerializer(many=True, read_only=True)
    machines = serializers.SerializerMethodField()

    class Meta(PartListSerializer.Meta):
        fields = [*PartListSerializer.Meta.fields, "description", "weight_kg", "stocks", "machines"]

    def get_machines(self, obj: Part) -> list[dict]:
        """Модели техники, к которым подходит запчасть."""
        return [
            {"slug": item.machine.slug, "name": str(item.machine), "note": item.note}
            for item in obj.applicability.select_related("machine", "machine__brand")
        ]
