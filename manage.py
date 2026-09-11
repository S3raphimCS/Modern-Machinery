#!/usr/bin/env python
"""Точка входа для команд управления Django."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Не удалось импортировать Django. Убедитесь, что виртуальное окружение "
            "активировано, и зависимости установлены командой `uv sync`."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
