"""Idempotently create/align Administrator and DataEntry roles."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.roles import ROLE_PERMISSIONS, seed_roles


class Command(BaseCommand):
    """Provision the role/permission matrix without creating users."""

    help = "Create or align the Administrator and DataEntry groups (idempotent)."

    def handle(self, *args: object, **options: object) -> None:
        groups = seed_roles()
        for name in sorted(groups):
            permissions = ", ".join(ROLE_PERMISSIONS[name])
            self.stdout.write(f"{name}: {permissions}")
        self.stdout.write(self.style.SUCCESS("Roles are up to date."))
