"""Наборы запросов каталога.

Витринные выборки собраны здесь, а не размазаны по представлениям: и API, и
HTML-страницы обязаны отдавать один и тот же набор видимых позиций.
"""

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    TrigramWordSimilarity,
)
from django.db import models
from django.db.models.functions import Greatest

from apps.core.utils import transliterate


class VisibleQuerySet(models.QuerySet):
    """Общая логика видимости для публикуемых справочников."""

    def visible(self):
        return self.filter(is_active=True)


class MachineQuerySet(models.QuerySet):
    def visible(self):
        """Позиции, которые вообще можно показывать посетителю."""
        return self.filter(is_active=True, is_published=True)

    def with_listing_relations(self):
        """Предзагрузка всего, что нужно плитке каталога.

        Без неё листинг из 12 машин даёт классический N+1: отдельный запрос за
        брендом, типом и главной картинкой на каждую карточку.
        """
        return self.select_related("brand", "machine_type").prefetch_related("images", "stocks")

    def with_detail_relations(self):
        """Предзагрузка для карточки машины."""
        return self.select_related("brand", "machine_type").prefetch_related(
            "images",
            "documents",
            "categories",
            "stocks__branch",
            "specs__spec_key__group",
            "specs__value_option",
        )

    def search(self, query: str):
        """Поиск по каталогу: точный, затем по опечаткам, затем по транслитерации.

        Порядок важен. Сначала полнотекстовый поиск с весами — совпадение по
        названию модели важнее совпадения в описании: снабженец ищет «PC400», а
        не слова из маркетингового текста.

        Если точных совпадений нет, включается поиск по похожести написания:
        он находит «экскаватр» и «бульдозр» — то, как название реально набирают
        в спешке с телефона.

        Последним шагом запрос переводится в латиницу. Бренды в каталоге
        записаны латиницей, а ищут их и кириллицей: «Коматсу» должно приводить
        к Komatsu, иначе запрос уходит в пустоту.

        Запасные варианты идут именно по очереди, а не вперемешку: иначе
        похожие по написанию модели перебивали бы точное совпадение.
        """
        query = (query or "").strip()
        if not query:
            return self

        exact = self._full_text_search(query)
        if exact.exists():
            return exact

        fuzzy = self.fuzzy_search(query)
        if fuzzy.exists():
            return fuzzy

        latin = transliterate(query)
        if latin.casefold() != query.casefold():
            transliterated = self._full_text_search(latin)
            if transliterated.exists():
                return transliterated
            return self.fuzzy_search(latin)

        return fuzzy

    def _full_text_search(self, query: str):
        """Полнотекстовый поиск с ранжированием по весам полей."""
        search_query = SearchQuery(query, config="russian", search_type="websearch")
        return (
            self.filter(search_vector=search_query)
            .annotate(rank=SearchRank(models.F("search_vector"), search_query))
            .order_by("-rank", "sort_order", "name")
        )

    def fuzzy_search(self, query: str, threshold: float = 0.45):
        """Поиск по похожести написания.

        Сравнение пословное, а не по строке целиком: у машины полное название
        вида «Бульдозер Komatsu D155A-6», и похожесть короткого запроса со всей
        строкой размывается до нуля. Пословное сравнение берёт лучшее совпадение
        среди слов и находит «бульдозр».

        Порог 0.45 подобран по каталогу: «погрзчик» находит погрузчики, но
        «кран» не вытаскивает половину позиций за компанию.
        """
        similarity = Greatest(
            TrigramWordSimilarity(query, "name"),
            TrigramWordSimilarity(query, "full_name"),
            TrigramWordSimilarity(query, "series"),
        )
        return (
            self.annotate(similarity=similarity)
            .filter(similarity__gt=threshold)
            .order_by("-similarity", "sort_order", "name")
        )
