"""Bounded PostgreSQL readiness check."""

from __future__ import annotations

import logging
from typing import cast

from django.conf import settings
from django.db import DatabaseError, connections, transaction

_logger = logging.getLogger("mytrolley.health")


def database_is_ready() -> bool:
    """Execute a cheap query with a bounded statement timeout.

    The connection attempt is bounded by ``DB_CONNECT_TIMEOUT`` configured on
    the database connection. Logging deliberately excludes exception text,
    which can contain host/user details; only the exception class is recorded.
    """
    try:
        with transaction.atomic(using="default"), connections["default"].cursor() as cursor:
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                [str(settings.HEALTH_DB_STATEMENT_TIMEOUT_MS)],
            )
            cursor.execute("SELECT 1")
            row = cast(tuple[int, ...] | None, cursor.fetchone())
        return row == (1,)
    except DatabaseError as exc:
        _logger.warning(
            "health.ready.database_unavailable",
            extra={
                "event": "health.ready.database_unavailable",
                "error_type": exc.__class__.__name__,
            },
        )
        return False
