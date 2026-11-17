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
# ENABLE_API_DOCS controls URL registration; API_DOCS_PUBLIC controls whether
# those routes require a staff session.
ENABLE_API_DOCS = get_bool("ENABLE_API_DOCS", default=True)

# Allow opening Swagger UI without a staff session so the custom login flow can
# be tested from a genuinely anonymous browser. Set API_DOCS_PUBLIC=false to
# require staff access locally. Production forces this to false.
API_DOCS_PUBLIC = get_bool("API_DOCS_PUBLIC", default=True)
