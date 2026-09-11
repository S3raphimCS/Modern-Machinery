"""Расширения PostgreSQL, от которых зависит вся схема.

`pg_trgm` нужен для поиска по части артикула и по опечаткам, `unaccent` — для
корректного сравнения строк. Расширения ставятся отдельной миграцией, потому что
индексы `gin_trgm_ops` в других приложениях не создадутся без них.
"""

from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        TrigramExtension(),
        UnaccentExtension(),
    ]
