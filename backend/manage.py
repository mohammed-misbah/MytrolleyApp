#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - defensive bootstrap
        raise ImportError(
            "Couldn't import Django. Did you activate the virtual environment "
            "and install backend/requirements/development.txt?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
