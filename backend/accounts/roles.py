"""Reproducible role and permission provisioning."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

ROLE_ADMINISTRATOR = "Administrator"
ROLE_DATA_ENTRY = "DataEntry"

BUSINESS_PERMISSIONS: tuple[str, ...] = (
    "accounts.manage_users",
    "accounts.manage_catalog",
)

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    ROLE_ADMINISTRATOR: BUSINESS_PERMISSIONS,
    ROLE_DATA_ENTRY: ("accounts.manage_catalog",),
}

_PERMISSION_LABELS = {
    "manage_users": "Can manage users and roles",
    "manage_catalog": "Can manage catalog data",
}


def seed_roles(using: str = "default") -> dict[str, Group]:
    """Create/align the two assessment roles idempotently.

    The operation is intentionally declarative: each role ends up with exactly
    the permissions listed above, regardless of how many times it runs.
    """
    user_model = get_user_model()
    content_type = ContentType.objects.db_manager(using).get_for_model(
        user_model,
        for_concrete_model=True,
    )

    permissions: dict[str, Permission] = {}
    for codename, label in _PERMISSION_LABELS.items():
        permission, _ = Permission.objects.using(using).get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": label},
        )
        permissions[codename] = permission

    groups: dict[str, Group] = {}
    with transaction.atomic(using=using):
        for role_name, permission_names in ROLE_PERMISSIONS.items():
            group, _ = Group.objects.using(using).get_or_create(name=role_name)
            group.permissions.set(
                [permissions[name.rsplit(".", 1)[-1]] for name in permission_names]
            )
            groups[role_name] = group
    return groups


def user_has_business_permission(user: Any, permission: str) -> bool:
    """Check an authenticated, active user's business permission."""
    return bool(user and user.is_authenticated and user.is_active and user.has_perm(permission))
