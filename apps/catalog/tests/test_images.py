"""Тесты обработки изображений: превью, WebP и заглушки."""

import io

import pytest
from django.core.files.base import ContentFile
from PIL import Image

from apps.catalog.factories import MachineImageFactory
from apps.catalog.models import MachineImage
from apps.catalog.services.images import (
    THUMBNAIL_SIZE,
    make_placeholder,
    make_thumbnail,
    make_webp,
)

pytestmark = pytest.mark.django_db


def sample_jpeg(size=(2000, 1500)) -> bytes:
    image = Image.new("RGB", size, (120, 130, 140))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def test_placeholder_has_expected_size():
    data = make_placeholder("Komatsu PC400-8", "Экскаватор · Хабаровск")
    assert Image.open(io.BytesIO(data)).size == (1600, 1200)


def test_placeholder_renders_cyrillic():
    """Подпись на заглушке — на русском, поэтому шрифт обязан её нарисовать."""
    plain = make_placeholder("", "")
    titled = make_placeholder("Бульдозер Komatsu D155A-6", "Гусеничный · Хабаровск")
    assert titled != plain


def test_webp_is_smaller_than_source():
    """Ради этого WebP и вводился: то же изображение, меньше вес."""
    source = sample_jpeg()
    converted = make_webp(io.BytesIO(source))

    assert len(converted) < len(source)
    assert Image.open(io.BytesIO(converted)).format == "WEBP"


def test_thumbnail_fits_target_size():
    thumb = make_thumbnail(io.BytesIO(sample_jpeg()))
    width, height = Image.open(io.BytesIO(thumb)).size

    assert width <= THUMBNAIL_SIZE[0]
    assert height <= THUMBNAIL_SIZE[1]


def test_thumbnail_keeps_aspect_ratio():
    thumb = make_thumbnail(io.BytesIO(sample_jpeg((2000, 1000))))
    width, height = Image.open(io.BytesIO(thumb)).size
    assert abs(width / height - 2.0) < 0.05


def test_derivatives_built_on_save(machine):
    image = MachineImage(machine=machine, alt="Фото")
    image.image.save("test.jpg", ContentFile(sample_jpeg()), save=False)
    image.save()

    assert image.image_webp
    assert image.thumbnail
    assert image.thumbnail.name.endswith("-thumb.webp")


def test_derivatives_not_rebuilt_on_unrelated_save(machine):
    image = MachineImage(machine=machine)
    image.image.save("test.jpg", ContentFile(sample_jpeg()), save=False)
    image.save()
    first = image.thumbnail.name

    image.sort_order = 50
    image.save()

    assert image.thumbnail.name == first


def test_derivatives_rebuilt_when_image_replaced(machine):
    image = MachineImage(machine=machine)
    image.image.save("first.jpg", ContentFile(sample_jpeg()), save=False)
    image.save()
    first = image.thumbnail.name

    image.image.save("second.jpg", ContentFile(sample_jpeg((1200, 900))), save=True)

    image.refresh_from_db()
    assert image.thumbnail.name != first


def test_broken_image_does_not_break_saving(machine):
    """Потерянная карточка дороже, чем отсутствующее превью."""
    image = MachineImage(machine=machine)
    image.image.save("broken.jpg", ContentFile(b"not an image at all"), save=False)
    image.save()

    assert MachineImage.objects.filter(pk=image.pk).exists()
    assert not image.thumbnail


def test_display_url_prefers_webp(machine):
    image = MachineImage(machine=machine)
    image.image.save("test.jpg", ContentFile(sample_jpeg()), save=False)
    image.save()

    assert image.display_url.endswith(".webp")
    assert image.thumbnail_url.endswith("-thumb.webp")


def test_urls_fall_back_to_source(machine):
    """Без производных сайт показывает исходник, а не пустоту."""
    image = MachineImageFactory(machine=machine)
    MachineImage.objects.filter(pk=image.pk).update(image_webp="", thumbnail="")
    image.refresh_from_db()

    assert image.display_url == image.image.url
    assert image.thumbnail_url == image.image.url
