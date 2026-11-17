"""Local development settings. Never use these for production."""

from __future__ import annotations

from config.env import get_bool, get_list
from config.settings.base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = get_list(
    "DJANGO_ALLOWED_HOSTS",
    default=("localhost", "127.0.0.1", "[::1]"),
)

# Development may expose Swagger to anonymous local users for convenience.
# The views are still staff-only; this flag only controls URL registration.
ENABLE_API_DOCS = get_bool("ENABLE_API_DOCS", default=True)
