"""Обработка изображений техники.

Два разных дела в одном модуле, потому что оба опираются на Pillow и на один
набор размеров:

1. Генерация превью и копий в WebP. Фотографии спецтехники тяжёлые, а критерий
   приёмки требует PageSpeed 80+ на мобильном. Без превью в листинг уходит
   исходник на несколько мегабайт, и норматив недостижим в принципе.
2. Генерация заглушки для позиции без фотографии. Пустая плитка выглядит как
   поломка вёрстки, а заглушка с моделью и брендом читается как «фото пока
   нет» и не портит впечатление от каталога.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

# Размеры подобраны под вёрстку: карточка в листинге не превышает 420 CSS-px,
# на экране с двойной плотностью пикселей ей достаточно 840.
THUMBNAIL_SIZE = (840, 630)
FULL_SIZE = (1600, 1200)
WEBP_QUALITY = 82
JPEG_QUALITY = 86

PLACEHOLDER_SIZE = (1600, 1200)
FONT_PATH = Path(settings.BASE_DIR) / "static" / "fonts" / "Montserrat-Variable.ttf"

# Цвета из макета.
INK = (22, 24, 28)
RED = (221, 28, 43)
LIGHT = (237, 237, 237)
LIGHTER = (247, 247, 247)


def _load_font(size: int, weight: str = "Bold"):
    """Montserrat из репозитория. Без него текст на заглушке не нарисовать."""
    font = ImageFont.truetype(str(FONT_PATH), size)
    # Шрифт без вариативных осей рисуется обычным начертанием — это не ошибка.
    with contextlib.suppress(OSError, ValueError):
        font.set_variation_by_name(weight)
    return font


def _fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Вписывает изображение в размер, сохраняя пропорции."""
    result = image.copy()
    result.thumbnail(size, Image.Resampling.LANCZOS)
    return result


def make_webp(source, size: tuple[int, int] = FULL_SIZE) -> bytes:
    """Готовит копию в WebP: он весит на 25–35% меньше JPEG при том же качестве."""
    with Image.open(source) as image:
        image = image.convert("RGB")
        buffer = io.BytesIO()
        _fit(image, size).save(buffer, format="WEBP", quality=WEBP_QUALITY, method=6)
        return buffer.getvalue()


def make_thumbnail(source, size: tuple[int, int] = THUMBNAIL_SIZE) -> bytes:
    """Готовит превью для плитки каталога — тоже в WebP."""
    return make_webp(source, size)


def make_placeholder(
    title: str, subtitle: str = "", size: tuple[int, int] = PLACEHOLDER_SIZE
) -> bytes:
    """Рисует заглушку в стиле макета: диагональная штриховка и подпись."""
    width, height = size
    image = Image.new("RGB", size, LIGHTER)
    draw = ImageDraw.Draw(image)

    # Диагональная штриховка повторяет CSS-заглушку из макета, чтобы пустая
    # карточка и сгенерированная картинка не выглядели как два разных решения.
    step = 34
    for offset in range(-height, width, step * 2):
        draw.polygon(
            [
                (offset, height),
                (offset + step, height),
                (offset + step + height, 0),
                (offset + height, 0),
            ],
            fill=LIGHT,
        )

    bar_height = int(height * 0.26)
    draw.rectangle([0, height - bar_height, width, height], fill=INK)
    draw.rectangle([0, height - bar_height, width, height - bar_height + 10], fill=RED)

    title_font = _load_font(int(height * 0.075))
    draw.text(
        (int(width * 0.05), height - bar_height + int(bar_height * 0.28)),
        title[:38],
        font=title_font,
        fill=(255, 255, 255),
    )

    if subtitle:
        subtitle_font = _load_font(int(height * 0.036), weight="SemiBold")
        draw.text(
            (int(width * 0.05), height - int(bar_height * 0.28)),
            subtitle[:52].upper(),
            font=subtitle_font,
            fill=(150, 154, 160),
        )

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()
