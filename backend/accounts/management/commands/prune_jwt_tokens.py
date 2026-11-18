"""Prune expired authentication sessions and stale refresh-throttle counters."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import AuthSession, RefreshThrottle


class Command(BaseCommand):
    """Remove old session rows and inactive refresh-throttle counters.

    Consumed refresh tokens are tracked on the ``AuthSession`` row itself, so
    deleting rows whose absolute expiry has passed is enough to keep token
    bookkeeping bounded. A session whose expiry has not passed is never touched.
    """

    help = "Delete expired authentication sessions and stale refresh throttles."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Retention for expired sessions and inactive throttle rows (default: 7).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        days = int(options["days"])
        if days < 1:
            raise CommandError("Retention must be at least one day.")

        cutoff = timezone.now() - timedelta(days=days)
        expired_sessions, _ = AuthSession.objects.filter(expires_at__lt=cutoff).delete()
        stale_throttles, _ = RefreshThrottle.objects.filter(
            window_started_at__lt=cutoff, blocked_until__isnull=True
        ).delete()
        self.stdout.write(
            f"Pruned {expired_sessions} expired sessions and "
            f"{stale_throttles} stale refresh throttle rows."
        )
