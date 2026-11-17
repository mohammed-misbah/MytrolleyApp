"""Django-level error handlers, CSRF failure response and request helpers."""

from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views import defaults
from django.views.csrf import csrf_failure as default_csrf_failure

from core.context import REQUEST_ID_HEADER
from core.errors import build_error_payload

_security_logger = logging.getLogger("mytrolley.security")


def _is_api_request(request: HttpRequest) -> bool:
    return request.path.startswith("/api/")


def _json_response(
    request: HttpRequest,
    *,
    code: str,
    message: str,
    status: int,
) -> JsonResponse:
    payload = build_error_payload(request, code=code, message=message)
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "no-store"
    response[REQUEST_ID_HEADER] = payload["error"]["request_id"]
    return response


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    """Return the API error envelope for CSRF failures on /api/ routes.

    Non-API consumers (notably the Django admin) keep Django's HTML 403.
    ``reason`` is logged only as an event, never reflected to the client.
    """
    if _is_api_request(request):
        _security_logger.warning(
            "security.csrf.failed",
            extra={"event": "security.csrf.failed"},
        )
        return _json_response(
            request,
            code="CSRF_FAILED",
            message="CSRF verification failed.",
            status=403,
        )
    return default_csrf_failure(request, reason=reason)


def bad_request(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    """Handle malformed/unsafe requests consistently for API paths."""
    if _is_api_request(request):
        return _json_response(
            request,
            code="BAD_REQUEST",
            message="The request was rejected.",
            status=400,
        )
    return defaults.bad_request(request, exception)  # type: ignore[arg-type]


def permission_denied(
    request: HttpRequest,
    exception: Exception | None = None,
) -> HttpResponse:
    """Handle middleware-level 403 responses for API paths."""
    if _is_api_request(request):
        return _json_response(
            request,
            code="FORBIDDEN",
            message="You do not have permission to perform this action.",
            status=403,
        )
    return defaults.permission_denied(request, exception)  # type: ignore[arg-type]


def page_not_found(
    request: HttpRequest,
    exception: Exception | None = None,
) -> HttpResponse:
    """Handle unmatched API paths with the shared error envelope."""
    if _is_api_request(request):
        return _json_response(
            request,
            code="NOT_FOUND",
            message="The requested resource was not found.",
            status=404,
        )
    return defaults.page_not_found(request, exception)


def server_error(request: HttpRequest) -> HttpResponse:
    """Return a generic API 500; Django logs the traceback server-side."""
    if _is_api_request(request):
        return _json_response(
            request,
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            status=500,
        )
    return defaults.server_error(request)


# Documentation: Django resolves these callables by name from config.urls.
__all__ = [
    "bad_request",
    "csrf_failure",
    "page_not_found",
    "permission_denied",
    "server_error",
]
