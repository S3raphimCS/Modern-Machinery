"""Сериализаторы контентных сущностей."""

from rest_framework import serializers

from apps.content.models import NewsPost, Page, Vacancy


class PageSerializer(serializers.ModelSerializer):
    blocks = serializers.SerializerMethodField()

    class Meta:
        model = Page
        fields = [
            "id",
            "slug",
            "path",
            "title",
            "menu_title",
            "body",
            "blocks",
            "seo_title",
            "seo_description",
        ]

    def get_blocks(self, obj: Page) -> list[dict]:
        return [{"type": block.block_type, "payload": block.payload} for block in obj.blocks.all()]


class NewsPostSerializer(serializers.ModelSerializer):
    categories = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = NewsPost
        fields = [
            "id",
            "slug",
            "title",
            "excerpt",
            "body",
            "cover",
            "categories",
            "published_at",
            "url",
        ]


class VacancySerializer(serializers.ModelSerializer):
    branch = serializers.CharField(source="branch.city", read_only=True)
    department = serializers.CharField(source="department.name", read_only=True)
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Vacancy
        fields = [
            "id",
            "slug",
            "title",
            "branch",
            "department",
            "description",
            "requirements",
            "salary_note",
            "published_at",
            "url",
        ]
