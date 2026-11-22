"""Local development settings. Never use these for production."""

from __future__ import annotations

from datetime import timedelta

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

# Local-only: short-lived access tokens make the automatic refresh flow easy to
# exercise in a browser. Token issuance reads this setting directly (see
# accounts/tokens.py); SIMPLE_JWT is kept consistent. Refresh lifetime, rotation,
# CSRF and all production settings are untouched.
JWT_ACCESS_TOKEN_LIFETIME_SECONDS = 30
SIMPLE_JWT = {
    **SIMPLE_JWT,  # noqa: F405
    "ACCESS_TOKEN_LIFETIME": timedelta(seconds=30),
}
