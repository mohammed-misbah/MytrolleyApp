"""Signal wiring for role seeding and authentication-session invalidation."""

from __future__ import annotations

from typing import Any

from django.db.models.signals import post_migrate, post_save, pre_save
from django.dispatch import receiver

from accounts.models import AuthSession, User
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


@receiver(pre_save, sender=User, dispatch_uid="accounts.capture_security_state")
def capture_security_state(sender: Any, instance: User, **kwargs: object) -> None:
    """Remember the previous password hash and active flag before a save."""
    if instance.pk is None:
        instance.__dict__["_previous_password_hash"] = None
        instance.__dict__["_previous_is_active"] = None
        return
    previous = (
        sender._default_manager.filter(pk=instance.pk).values("password", "is_active").first()
    )
    instance.__dict__["_previous_password_hash"] = (
        previous["password"] if previous is not None else None
    )
    instance.__dict__["_previous_is_active"] = (
        previous["is_active"] if previous is not None else None
    )


@receiver(post_save, sender=User, dispatch_uid="accounts.revoke_sessions_on_change")
def revoke_sessions_on_security_change(
    sender: Any,
    instance: User,
    created: bool,
    **kwargs: object,
) -> None:
    """Revoke all sessions after a password change or account deactivation."""
    if created:
        return

    previous_password = instance.__dict__.get("_previous_password_hash")
    previous_active = instance.__dict__.get("_previous_is_active")

    reason: str | None = None
    if previous_password and instance.password != previous_password:
        reason = AuthSession.RevokeReason.PASSWORD_CHANGED
    elif previous_active is True and instance.is_active is False:
        reason = AuthSession.RevokeReason.ACCOUNT_DEACTIVATED

    if reason is None:
        return

    # Imported lazily to avoid an accounts.tokens -> accounts.models import
    # cycle at app-loading time.
    from accounts.tokens import revoke_user_sessions

    revoke_user_sessions(instance.pk, reason=reason)
