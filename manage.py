#!/usr/bin/env python
"""Django's command-line entry point for the local TilTale authoring app."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as error:
        raise ImportError(
            "Django is not installed. Activate .venv and run "
            "'python -m pip install -r requirements.txt'."
        ) from error
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
