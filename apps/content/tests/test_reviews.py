"""Тесты отзывов и рейтингов на внешних площадках."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.content.models import Review, ReviewSource

pytestmark = pytest.mark.django_db


def make_review(**overrides) -> Review:
    data = {
        "author_name": "Ковалёв Сергей",
        "author_position": "главный механик",
        "company": "ООО «Амурстрой»",
        "city": "Хабаровск",
        "rating": 5,
        "text": "Привезли за три недели, претензий нет.",
        "is_published": True,
        "published_at": timezone.now(),
    }
    data.update(overrides)
    return Review.objects.create(**data)


def test_review_page_shows_published(client, branch):
    make_review()
    make_review(author_name="Черновик", is_published=False)

    content = client.get(reverse("content:review-list")).content.decode()

    assert "Ковалёв Сергей" in content
    assert "Черновик" not in content


def test_signature_joins_position_company_city():
    review = make_review()

    assert review.signature == "главный механик, ООО «Амурстрой», Хабаровск"


def test_signature_skips_empty_parts():
    review = make_review(author_position="", city="")

    assert review.signature == "ООО «Амурстрой»"


@pytest.mark.parametrize("rating", [0, 6])
def test_rating_must_be_between_one_and_five(rating):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_review(rating=rating)


def test_review_page_has_no_microdata(client, branch):
    """Отзыв организации о самой себе не даёт звёзд и нарушал бы правила."""
    make_review()

    content = client.get(reverse("content:review-list")).content.decode()

    assert "schema.org/Review" not in content
    assert "AggregateRating" not in content


def test_review_appears_on_the_machine_card_with_microdata(client, machine):
    """На карточке техники разметка законна: это отзыв о товаре."""
    make_review(machine=machine)

    content = client.get(machine.get_absolute_url()).content.decode()

    assert "Ковалёв Сергей" in content
    assert 'itemtype="https://schema.org/Review"' in content
    assert 'itemprop="ratingValue" content="5"' in content


def test_unpublished_review_not_on_the_card(client, machine):
    make_review(machine=machine, is_published=False)

    assert "Ковалёв Сергей" not in client.get(machine.get_absolute_url()).content.decode()


def test_card_without_reviews_has_no_block(client, machine):
    assert "Отзывы об этой модели" not in client.get(machine.get_absolute_url()).content.decode()


def test_platform_ratings_are_shown_with_links(client, branch):
    ReviewSource.objects.create(
        platform=ReviewSource.Platform.GIS,
        rating="4.4",
        reviews_count=17,
        url="https://2gis.ru/khabarovsk",
    )

    content = client.get(reverse("content:review-list")).content.decode()

    assert "2ГИС" in content
    assert "4.4" in content
    assert "https://2gis.ru/khabarovsk" in content


def test_google_is_supported_as_a_platform(client, branch):
    """Google учтён, но карточка показывается без оценки — одной ссылкой."""
    ReviewSource.objects.create(
        platform=ReviewSource.Platform.GOOGLE,
        url="https://maps.google.com/x",
    )

    assert "Google" in client.get(reverse("content:review-list")).content.decode()


def test_inactive_platform_is_hidden(client, branch):
    ReviewSource.objects.create(
        platform=ReviewSource.Platform.GOOGLE,
        url="https://maps.google.com/x",
        is_active=False,
    )

    assert "Google" not in client.get(reverse("content:review-list")).content.decode()


def test_rating_is_not_localised_in_markup(client, branch):
    """Дробный рейтинг выводится с точкой: запятая ломала бы ссылки и разметку."""
    ReviewSource.objects.create(
        platform=ReviewSource.Platform.YANDEX,
        rating="4.6",
        reviews_count=23,
        url="https://yandex.ru/maps/x",
    )

    content = client.get(reverse("content:review-list")).content.decode()

    assert "4.6" in content
    assert "4,6" not in content


def test_one_row_per_platform():
    """Вторая строка для той же площадки отсекается проверкой модели."""
    ReviewSource.objects.create(platform="2gis", rating="4.4", url="https://2gis.ru/khabarovsk")

    with pytest.raises(ValidationError):
        ReviewSource.objects.create(platform="2gis", rating="4.5", url="https://2gis.ru/other")


def test_one_row_per_platform_enforced_by_database():
    """И на уровне базы — на случай записи в обход проверки модели."""
    ReviewSource.objects.create(platform="2gis", rating="4.4", url="https://2gis.ru/khabarovsk")

    with pytest.raises(IntegrityError), transaction.atomic():
        ReviewSource.objects.bulk_create(
            [ReviewSource(platform="2gis", rating="4.5", url="https://2gis.ru/other")]
        )


def test_widget_code_must_be_a_yandex_widget():
    """Поле выводится без экранирования, поэтому принимает только виджет."""
    with pytest.raises(ValidationError, match="виджет"):
        ReviewSource.objects.create(
            platform="yandex",
            rating="4.6",
            url="https://2gis.ru/khabarovsk",
            widget_code="<script>alert(1)</script>",
        )


def test_widget_code_rejects_foreign_iframe():
    with pytest.raises(ValidationError, match="виджет"):
        ReviewSource.objects.create(
            platform="yandex",
            rating="4.6",
            url="https://2gis.ru/khabarovsk",
            widget_code='<iframe src="https://evil.example/x"></iframe>',
        )


def test_valid_widget_code_is_accepted():
    source = ReviewSource.objects.create(
        platform="yandex",
        rating="4.6",
        url="https://2gis.ru/khabarovsk",
        widget_code='<iframe src="https://yandex.ru/maps-reviews-widget/1"></iframe>',
    )

    assert source.pk is not None


def test_empty_widget_code_is_allowed():
    """Для 2ГИС и Google виджета нет — поле просто пустое."""
    source = ReviewSource.objects.create(
        platform="2gis", rating="4.4", url="https://2gis.ru/khabarovsk"
    )

    assert source.widget_code == ""


def test_yandex_widget_is_rendered_when_present(client, branch):
    ReviewSource.objects.create(
        platform=ReviewSource.Platform.YANDEX,
        rating="4.6",
        reviews_count=23,
        url="https://yandex.ru/maps/x",
        widget_code='<iframe src="https://yandex.ru/maps-reviews-widget/1"></iframe>',
    )

    content = client.get(reverse("content:review-list")).content.decode()

    assert "maps-reviews-widget" in content


def test_google_rating_is_rejected():
    """Оценку Google нельзя переносить на свой сайт — только ссылка.

    Поле блокируется в модели, а не в шаблоне: иначе заполнивший его в
    админке решил бы, что цифра появилась на странице.
    """
    source = ReviewSource(
        platform=ReviewSource.Platform.GOOGLE,
        rating=Decimal("4.7"),
        url="https://maps.google.com/?cid=1",
    )

    with pytest.raises(ValidationError) as excinfo:
        source.save()

    assert "rating" in excinfo.value.message_dict


def test_google_card_is_saved_without_a_rating():
    source = ReviewSource.objects.create(
        platform=ReviewSource.Platform.GOOGLE,
        url="https://maps.google.com/?cid=1",
    )

    assert source.rating is None


def test_google_card_shows_a_link_instead_of_a_number(client, branch):
    ReviewSource.objects.create(
        platform=ReviewSource.Platform.GOOGLE,
        url="https://maps.google.com/?cid=1",
    )
    ReviewSource.objects.create(
        platform=ReviewSource.Platform.GIS,
        rating=Decimal("4.4"),
        reviews_count=17,
        url="https://2gis.ru/khabarovsk/firm/1",
    )

    body = client.get(reverse("content:review-list")).content.decode()

    assert "4,4" in body or "4.4" in body
    assert "4,7" not in body and "4.7" not in body
    assert "смотреть отзывы" in body
