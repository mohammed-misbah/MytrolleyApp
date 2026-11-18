"""Accounts application configuration."""

from __future__ import annotations

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Custom user, authentication and role configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self) -> None:
        """Register role seeding and the OpenAPI Bearer security scheme."""
        from accounts import schema, signals  # noqa: F401
