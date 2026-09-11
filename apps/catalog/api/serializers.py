"""Сериализаторы каталога техники."""

from rest_framework import serializers

from apps.catalog.models import (
    Brand,
    Category,
    Machine,
    MachineDocument,
    MachineImage,
    MachineStock,
    MachineType,
)


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "slug", "name", "logo", "description", "sort_order"]


class CategorySerializer(serializers.ModelSerializer):
    depth = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "slug", "name", "description", "image", "depth"]


class MachineTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineType
        fields = ["id", "slug", "name", "name_plural", "icon"]


class MachineImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineImage
        fields = ["id", "image", "alt", "is_main", "sort_order"]


class MachineDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineDocument
        fields = ["id", "kind", "title", "file", "file_size"]


class MachineStockSerializer(serializers.ModelSerializer):
    """Наличие для публичного API.

    Точное количество наружу не отдаётся: заказчик не готов показывать
    конкурентам остатки склада. Публичный контракт — статус и срок готовности.
    """

    branch = serializers.CharField(source="branch.city", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = MachineStock
        fields = ["branch", "status", "status_display", "lead_time"]


class MachineSpecValueSerializer(serializers.Serializer):
    """Характеристика в развёрнутом виде."""

    code = serializers.CharField()
    name = serializers.CharField()
    group = serializers.CharField()
    unit = serializers.CharField()
    value = serializers.CharField()


class MachineListSerializer(serializers.ModelSerializer):
    brand = serializers.CharField(source="brand.name", read_only=True)
    brand_slug = serializers.SlugField(source="brand.slug", read_only=True)
    machine_type = serializers.CharField(source="machine_type.name", read_only=True)
    main_image = serializers.SerializerMethodField()
    stock_status = serializers.CharField(read_only=True)
    display_price = serializers.CharField(read_only=True)
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Machine
        fields = [
            "id",
            "slug",
            "name",
            "full_name",
            "series",
            "brand",
            "brand_slug",
            "machine_type",
            "short_description",
            "specs_cache",
            "main_image",
            "stock_status",
            "display_price",
            "is_featured",
            "url",
        ]

    def get_main_image(self, obj: Machine) -> str | None:
        image = obj.main_image
        if image is None or not image.image:
            return None
        request = self.context.get("request")
        url = image.image.url
        return request.build_absolute_uri(url) if request else url


class MachineDetailSerializer(MachineListSerializer):
    images = MachineImageSerializer(many=True, read_only=True)
    documents = MachineDocumentSerializer(many=True, read_only=True)
    stocks = MachineStockSerializer(many=True, read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    specs = serializers.SerializerMethodField()

    class Meta(MachineListSerializer.Meta):
        fields = [
            *MachineListSerializer.Meta.fields,
            "description",
            "equipment",
            "warranty_note",
            "price",
            "price_note",
            "is_price_on_request",
            "images",
            "documents",
            "stocks",
            "categories",
            "specs",
            "seo_title",
            "seo_description",
        ]

    def get_specs(self, obj: Machine) -> list[dict]:
        return [
            {
                "code": spec.spec_key.code,
                "name": spec.spec_key.name,
                "group": spec.spec_key.group.name,
                "unit": spec.spec_key.unit,
                "value": spec.display_value,
            }
            for spec in obj.specs.all()
        ]
