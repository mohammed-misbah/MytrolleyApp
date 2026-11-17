"""Central DRF exception normalization.

Every API failure returns the documented ``{"error": {...}}`` envelope with a
stable code, a safe message and the request ID. Internal details and stack
traces stay in server logs.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
)
from django.core.exceptions import (
    RequestDataTooBig,
    SuspiciousOperation,
)
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAcceptable,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.response import Response

from core.errors import (
    GENERIC_ERROR_MESSAGE,
    VALIDATION_MESSAGE,
    api_error_response,
    normalize_validation_errors,
)
from core.exceptions import InvalidCredentials, LoginRateLimited

_logger = logging.getLogger("mytrolley.api")
_security_logger = logging.getLogger("mytrolley.security")


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Normalize DRF, Django and unexpected exceptions for API routes."""
    request = context.get("request")
    view = context.get("view")

    if isinstance(exc, LoginRateLimited):
        return api_error_response(
            request,
            code=exc.api_code,
            message=str(exc.detail),
            status=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    if isinstance(exc, InvalidCredentials):
        return api_error_response(
            request,
            code=exc.api_code,
            message=str(exc.detail),
            status=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    if isinstance(exc, ValidationError):
        return api_error_response(
            request,
            code="VALIDATION_ERROR",
            message=VALIDATION_MESSAGE,
            status=status.HTTP_400_BAD_REQUEST,
            fields=normalize_validation_errors(exc.detail),
        )

    if isinstance(exc, ParseError):
        return api_error_response(
            request,
            code="INVALID_JSON",
            message="Request body could not be parsed as JSON.",
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, UnsupportedMediaType):
        return api_error_response(
            request,
            code="UNSUPPORTED_MEDIA_TYPE",
            message="Content-Type must be application/json.",
            status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    if isinstance(exc, NotAcceptable):
        return api_error_response(
            request,
            code="NOT_ACCEPTABLE",
            message="The requested response format is not available.",
            status=status.HTTP_406_NOT_ACCEPTABLE,
        )

    if isinstance(exc, AuthenticationFailed):
        return api_error_response(
            request,
            code=getattr(exc, "api_code", "AUTHENTICATION_FAILED"),
            message="Authentication failed.",
            status=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Session"},
        )

    if isinstance(exc, NotAuthenticated):
        return api_error_response(
            request,
            code="UNAUTHENTICATED",
            message="Authentication credentials were not provided.",
            status=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Session"},
        )

    if isinstance(exc, PermissionDenied):
        csrf_failure = "CSRF" in str(exc.detail)
        if csrf_failure:
            _security_logger.warning(
                "security.csrf.failed",
                extra={"event": "security.csrf.failed"},
            )
        return api_error_response(
            request,
            code="CSRF_FAILED" if csrf_failure else "FORBIDDEN",
            message=(
                "CSRF verification failed."
                if csrf_failure
                else "You do not have permission to perform this action."
            ),
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, NotFound):
        return api_error_response(
            request,
            code="NOT_FOUND",
            message="The requested resource was not found.",
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, MethodNotAllowed):
        return api_error_response(
            request,
            code="METHOD_NOT_ALLOWED",
            message="This HTTP method is not allowed for the requested resource.",
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    if isinstance(exc, Throttled):
        wait = getattr(exc, "wait", None)
        retry_after = int(wait) if wait is not None else 60
        return api_error_response(
            request,
            code="RATE_LIMITED",
            message="Too many requests. Please try again later.",
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(max(1, retry_after))},
        )

    if isinstance(exc, Http404):
        return api_error_response(
            request,
            code="NOT_FOUND",
            message="The requested resource was not found.",
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, DjangoPermissionDenied):
        return api_error_response(
            request,
            code="FORBIDDEN",
            message="You do not have permission to perform this action.",
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, RequestDataTooBig):
        return api_error_response(
            request,
            code="PAYLOAD_TOO_LARGE",
            message="Request body is too large.",
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    if isinstance(exc, SuspiciousOperation):
        return api_error_response(
            request,
            code="BAD_REQUEST",
            message="The request was rejected.",
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, APIException):
        return api_error_response(
            request,
            code=getattr(exc, "api_code", "API_ERROR"),
            message=GENERIC_ERROR_MESSAGE,
            status=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    # Unexpected failures are logged with a full traceback but never exposed.
    _logger.exception(
        "api.unhandled_exception",
        extra={
            "event": "api.unhandled_exception",
            "view": getattr(view, "__class__", type(view)).__name__ if view else None,
        },
    )
    return api_error_response(
        request,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred.",
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
