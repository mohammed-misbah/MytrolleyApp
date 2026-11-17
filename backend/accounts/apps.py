"""Accounts application configuration."""

from __future__ import annotations

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Custom user, authentication and role configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self) -> None:
        """Register post-migration role seeding."""
        from accounts import signals  # noqa: F401
