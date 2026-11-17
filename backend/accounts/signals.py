"""Signal wiring that keeps roles present after every migration."""

from __future__ import annotations

from typing import Any

from django.db.models.signals import post_migrate
from django.dispatch import receiver

from accounts.roles import seed_roles


@receiver(post_migrate, dispatch_uid="accounts.seed_roles_after_migrate")
def seed_roles_after_migrate(sender: Any, using: str = "default", **kwargs: object) -> None:
    """Seed roles once for the accounts app after migrations complete.

    The receiver is idempotent. Filtering by sender avoids repeating the work
    for every installed app's post_migrate emission.
    """
    if getattr(sender, "label", None) != "accounts":
        return
    seed_roles(using=using)
