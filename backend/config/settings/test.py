"""Test settings: PostgreSQL, deterministic and fast password hashing.

Security behaviour is not disabled to make tests pass. Cookie ``Secure`` flags
are false only because Django's test client speaks plain HTTP; production
settings are separately validated.
"""

from __future__ import annotations

from config.settings.base import *  # noqa: F403

DEBUG = False

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# Fast hashing keeps integration tests quick. It is never used outside tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

ENABLE_API_DOCS = True

# Automated tests must never write to a real bucket. Always use temporary local
# storage here, regardless of a developer's .env or process environment.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
