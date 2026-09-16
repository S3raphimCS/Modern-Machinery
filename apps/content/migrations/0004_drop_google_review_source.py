"""У хабаровского филиала нет карточки с отзывами в Google.

Площадка убрана из списка целиком, а рейтинг снова обязателен: он остался
необязательным только ради Google, которому оценку показывать было нельзя.
"""

from django.db import migrations, models


def drop_google_sources(apps, schema_editor):
    """Убирает записи площадки, которой больше нет в списке.

    Иначе рейтинг не вернуть в обязательный: у такой записи он пустой.
    """
    ReviewSource = apps.get_model("content", "ReviewSource")
    ReviewSource.objects.filter(platform="google").delete()


def restore_google_platform(apps, schema_editor):
    """Откат ничего не восстанавливает: удалённые записи не воссоздать."""


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0003_remove_reviewsource_reviewsource_rating_in_range_and_more"),
    ]

    operations = [
        migrations.RunPython(drop_google_sources, restore_google_platform),
        migrations.RemoveConstraint(
            model_name="reviewsource",
            name="reviewsource_rating_in_range",
        ),
        migrations.AlterField(
            model_name="reviewsource",
            name="platform",
            field=models.CharField(
                choices=[("yandex", "Яндекс Карты"), ("2gis", "2ГИС")],
                max_length=16,
                unique=True,
                verbose_name="Площадка",
            ),
        ),
        migrations.AlterField(
            model_name="reviewsource",
            name="rating",
            field=models.DecimalField(decimal_places=1, max_digits=2, verbose_name="Рейтинг"),
        ),
        migrations.AlterField(
            model_name="reviewsource",
            name="reviews_count",
            field=models.PositiveIntegerField(default=0, verbose_name="Число оценок"),
        ),
        migrations.AddConstraint(
            model_name="reviewsource",
            constraint=models.CheckConstraint(
                condition=models.Q(("rating__gte", 0), ("rating__lte", 5)),
                name="reviewsource_rating_in_range",
            ),
        ),
    ]
