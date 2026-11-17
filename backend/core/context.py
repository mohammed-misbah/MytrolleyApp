"""Per-request identifier context used by logging and error envelopes."""

from __future__ import annotations

import re
import secrets
from contextvars import ContextVar, Token

from django.http import HttpRequest

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_META_KEY = "HTTP_X_REQUEST_ID"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_REQUEST_ID_FALLBACK = "-"

_request_id_context: ContextVar[str] = ContextVar(
    "request_id",
    default=_REQUEST_ID_FALLBACK,
)


def new_request_id() -> str:
    """Generate an unguessable, log-safe request identifier."""
    return secrets.token_hex(16)


def normalize_request_id(candidate: str) -> str:
    """Accept a bounded, log-safe client ID or replace it with a new one."""
    if REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return new_request_id()


def set_request_id(value: str) -> Token[str]:
    """Bind a request ID to the current execution context."""
    return _request_id_context.set(value)


def reset_request_id(token: Token[str]) -> None:
    """Restore the previous context value."""
    _request_id_context.reset(token)


def get_request_id(request: HttpRequest | None = None) -> str:
    """Return the request's ID, falling back to the logging context."""
    if request is not None:
        value = getattr(request, "request_id", None)
        if isinstance(value, str) and value:
            return value
    return _request_id_context.get()
