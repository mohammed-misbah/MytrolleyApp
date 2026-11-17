"""Core app: shared error handling, logging, health and request utilities."""

from __future__ import annotations

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Application configuration for shared infrastructure."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
