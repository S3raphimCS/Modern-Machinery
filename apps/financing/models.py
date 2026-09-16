"""Лизинг и кредит: партнёры и условия финансирования."""

from decimal import ROUND_HALF_UP, Decimal

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import SortableMixin, TimeStampedModel

# Ключ кэша условий: объявлен здесь, чтобы модель могла его сбрасывать,
# а шаблонный тег — читать, без кругового импорта.
TERMS_CACHE_KEY = "financing:terms:v1"


class LeasingPartner(TimeStampedModel, SortableMixin):
    """Лизинговая или кредитная организация, с которой работает филиал."""

    name = models.CharField("Название", max_length=160)
    logo = models.ImageField("Логотип", upload_to="partners/", blank=True, null=True)
    url = models.URLField("Сайт", blank=True)
    note = models.CharField(
        "Примечание",
        max_length=200,
        blank=True,
        help_text="Например: «спецпрограмма на технику Komatsu».",
    )
    is_active = models.BooleanField("Активен", default=True, db_index=True)

    class Meta:
        verbose_name = "Партнёр по финансированию"
        verbose_name_plural = "Партнёры по финансированию"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class LeasingTerms(models.Model):
    """Условия финансирования: синглтон.

    Эти же значения служат границами и значениями по умолчанию для
    калькулятора. Менеджер меняет «аванс от 10%» в админке — и калькулятор
    сразу считает по новым правилам, без участия разработчика.
    """

    min_advance_percent = models.PositiveSmallIntegerField("Аванс от, %", default=10)
    max_advance_percent = models.PositiveSmallIntegerField("Аванс до, %", default=49)
    # Минимум единица: срок в ноль месяцев прошёл бы в админке, а потом
    # уронил бы расчёт прямо в плитке каталога — делением на ноль.
    min_months = models.PositiveSmallIntegerField(
        "Срок от, месяцев", default=12, validators=[MinValueValidator(1)]
    )
    max_months = models.PositiveSmallIntegerField(
        "Срок до, месяцев", default=60, validators=[MinValueValidator(1)]
    )
    default_markup_percent = models.DecimalField(
        "Удорожание по умолчанию, % в год",
        max_digits=5,
        decimal_places=2,
        default=7,
        help_text="Ориентир для калькулятора. Точную ставку называет "
        "лизинговая компания после рассмотрения заявки.",
    )
    decision_days = models.CharField("Срок решения", max_length=60, default="1–3 дня")
    intro = models.TextField("Текст раздела", blank=True)
    is_credit_available = models.BooleanField("Доступен кредит", default=True)

    class Meta:
        verbose_name = "Условия финансирования"
        verbose_name_plural = "Условия финансирования"
        constraints = [
            # Перевёрнутые границы сделали бы калькулятор неработоспособным:
            # ползунок с минимумом больше максимума не имеет смысла.
            models.CheckConstraint(
                name="leasingterms_advance_range_ordered",
                condition=models.Q(max_advance_percent__gte=models.F("min_advance_percent")),
            ),
            models.CheckConstraint(
                name="leasingterms_months_range_ordered",
                condition=models.Q(max_months__gte=models.F("min_months")),
            ),
            models.CheckConstraint(
                name="leasingterms_months_positive",
                condition=models.Q(min_months__gte=1),
            ),
        ]

    def __str__(self) -> str:
        return "Условия финансирования"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Плитка каталога считает платёж по кэшированным условиям. Без сброса
        # она до десяти минут показывала бы платёж по старым правилам, а
        # страница лизинга — уже по новым.
        cache.delete(TERMS_CACHE_KEY)

    def clean(self) -> None:
        if not self.pk and LeasingTerms.objects.exists():
            raise ValidationError("Условия уже заведены — отредактируйте существующие.")
        if self.max_advance_percent > 100:
            raise ValidationError({"max_advance_percent": "Аванс не может превышать 100%."})

    @classmethod
    def load(cls) -> "LeasingTerms":
        """Отдаёт условия, создавая их при первом обращении.

        Через `get_or_create`, а не «посмотреть и создать»: на свежем сервере
        таблица пуста, кэш холодный, и параллельные запросы к каталогу
        создавали бы строку одновременно. Вторая попытка упиралась бы в
        проверку синглтона и роняла страницу с ошибкой сервера.
        """
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def default_advance_percent(self) -> int:
        """Значение ползунка аванса при открытии калькулятора."""
        return self.min_advance_percent

    @property
    def default_months(self) -> int:
        """Срок по умолчанию — середина допустимого диапазона, кратная году.

        Округление обычное, а не банковское: у диапазона 0–60 середина
        приходится ровно на 2,5 года, и `round` вернул бы 24 месяца вместо
        ожидаемых 36.
        """
        middle = Decimal(self.min_months + self.max_months) / 2
        years = (middle / 12).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        rounded = int(years) * 12
        return min(max(rounded, self.min_months), self.max_months)
