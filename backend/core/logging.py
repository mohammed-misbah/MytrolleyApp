"""JSON log formatting with allowlisted structured fields."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from core.context import get_request_id

_ALLOWED_EXTRA_FIELDS = (
    "event",
    "method",
    "path",
    "status",
    "duration_ms",
    "reason",
    "retry_after",
    "user_id",
    "error_type",
)


class JsonFormatter(logging.Formatter):
    """Render one JSON object per log record.

    Arbitrary ``extra`` values are not serialized: only known operational and
    security fields are included, reducing the chance of leaking credentials
    or request data accidentally attached to a record.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id and request_id != "-":
            payload["request_id"] = request_id
        for field in _ALLOWED_EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)
