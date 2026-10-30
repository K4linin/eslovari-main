#!/usr/bin/env python
"""Утилита управления проектом eslovari.ru."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "electronic_dictionary.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django не найден. Активируйте виртуальное окружение и выполните "
            "pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
