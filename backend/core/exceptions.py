"""Application-specific API exceptions with stable machine-readable codes."""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException


class PayloadTooLarge(APIException):
    """Raised when a JSON request body exceeds the configured limit."""

    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "Request body is too large."
    default_code = "payload_too_large"
    api_code = "PAYLOAD_TOO_LARGE"


class InvalidCredentials(APIException):
    """Generic credential failure that never reveals account existence."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid username or password."
    default_code = "invalid_credentials"
    api_code = "INVALID_CREDENTIALS"

    def __init__(self, detail: Any = None, code: Any = None) -> None:
        super().__init__(detail, code)
        self.headers = {"WWW-Authenticate": "Session"}


class LoginRateLimited(APIException):
    """Temporary, database-backed login cooldown."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many authentication attempts. Please try again later."
    default_code = "rate_limited"
    api_code = "RATE_LIMITED"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__()
        self.retry_after_seconds = max(1, retry_after_seconds)
        self.headers = {"Retry-After": str(self.retry_after_seconds)}
