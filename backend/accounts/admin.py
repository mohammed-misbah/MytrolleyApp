"""Restricted Django admin registration for the custom user model."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Staff-only account administration; roles remain Django groups."""

    list_display = (
        "username",
        "email",
        "is_staff",
        "is_active",
        "is_superuser",
    )
    search_fields = ("username", "email")
    ordering = ("username",)
