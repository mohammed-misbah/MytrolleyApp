"""Request ID, structured request logging and admin network allowlisting."""

from __future__ import annotations

import ipaddress
import logging
import time
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponseForbidden
from django.http.response import HttpResponseBase

from core.context import (
    REQUEST_ID_HEADER,
    REQUEST_ID_META_KEY,
    normalize_request_id,
    reset_request_id,
    set_request_id,
)
from core.security import get_client_ip

_request_logger = logging.getLogger("mytrolley.request")


class RequestIdMiddleware:
    """Attach a validated or generated request ID to every request/response."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        candidate = request.META.get(REQUEST_ID_META_KEY, "")
        request_id = normalize_request_id(candidate)
        request.request_id = request_id  # type: ignore[attr-defined]
        token = set_request_id(request_id)
        try:
            response = self.get_response(request)
            response[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            reset_request_id(token)


class RequestLoggingMiddleware:
    """Log method, safe path, status and timing without bodies or credentials.

    This is an outer wrapper so an exception that becomes Django's 500 response
    still leaves a diagnostic stack trace in protected server logs.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        started = time.perf_counter()
        try:
            response = self.get_response(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            _request_logger.exception(
                "request.unhandled_exception",
                extra={
                    "event": "request.unhandled_exception",
                    "method": request.method,
                    "path": request.path,
                    "status": 500,
                    "duration_ms": duration_ms,
                },
            )
            raise
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        level = logging.INFO
        if response.status_code >= 500:
            level = logging.ERROR
        elif response.status_code >= 400:
            level = logging.WARNING
        _request_logger.log(
            level,
            "request.completed",
            extra={
                "event": "request.completed",
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


class AdminIpAllowlistMiddleware:
    """Optionally restrict the Django admin to configured source networks.

    The allowlist is a defence-in-depth control for deployments where admin
    access can be limited to an office/VPN egress range. Django still requires
    an authenticated staff user.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        entries = settings.ADMIN_ALLOWED_IPS
        admin_prefix = f"/{settings.ADMIN_URL}"
        if entries and request.path.startswith(admin_prefix):
            client_ip = get_client_ip(request)
            if not _ip_is_allowed(client_ip, entries):
                return HttpResponseForbidden(
                    "Forbidden.",
                    content_type="text/plain; charset=utf-8",
                )
        return self.get_response(request)


def _ip_is_allowed(client_ip: str, entries: tuple[str, ...]) -> bool:
    try:
        address = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for entry in entries:
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            continue
        if address in network:
            return True
    return False
