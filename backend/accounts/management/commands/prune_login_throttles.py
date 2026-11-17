"""Remove stale login-throttle rows to keep the table bounded."""

from __future__ import annotations

import argparse
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from accounts.models import LoginThrottle


class Command(BaseCommand):
    """Delete old, non-blocking throttle rows."""

    help = "Delete login throttle rows older than N days (default 7)."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args: object, **options: object) -> None:
        days = int(str(options["days"]))
        if days < 1:
            raise ValueError("--days must be at least 1")
        now = timezone.now()
        cutoff = now - timedelta(days=days)
        deleted, _ = (
            LoginThrottle.objects.filter(
                updated_at__lt=cutoff,
            )
            .filter(Q(blocked_until__isnull=True) | Q(blocked_until__lt=now))
            .delete()
        )
        self.stdout.write(f"Deleted {deleted} stale login throttle row(s).")
