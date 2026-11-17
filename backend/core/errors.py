"""Shared API error envelope and Django-level JSON handlers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.http import HttpRequest, JsonResponse
from rest_framework.response import Response

from core.context import get_request_id, new_request_id

VALIDATION_MESSAGE = "Please correct the supplied values."
GENERIC_ERROR_MESSAGE = "The request could not be completed."


def resolved_request_id(request: HttpRequest | None = None) -> str:
    """Always return a non-empty request ID for an error payload."""
    value = get_request_id(request)
    return value if value and value != "-" else new_request_id()


def normalize_validation_errors(detail: Any, prefix: str = "") -> dict[str, list[str]]:
    """Flatten DRF validation details into ``field -> messages``.

    Nested serializer errors use dotted keys. A list at the top level is
    reported under ``non_field_errors``.
    """
    fields: dict[str, list[str]] = {}

    def add(key: str, messages: list[str]) -> None:
        if not messages:
            return
        fields.setdefault(key, []).extend(messages)

    def walk(value: Any, key: str) -> None:
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                normalized_key = (
                    "non_field_errors" if child_key == "non_field_errors" else str(child_key)
                )
                dotted = f"{key}.{normalized_key}" if key else normalized_key
                walk(child_value, dotted)
            return
        if isinstance(value, (list, tuple)):
            messages = [str(item) for item in value if str(item)]
            add(key or "non_field_errors", messages)
            return
        add(key or "non_field_errors", [str(value)])

    walk(detail, prefix)
    return fields


def build_error_payload(
    request: HttpRequest | None,
    *,
    code: str,
    message: str,
    fields: dict[str, list[str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build the single documented error contract."""
    return {
        "error": {
            "code": code,
            "message": message,
            "fields": fields or {},
            "request_id": resolved_request_id(request),
        }
    }


def api_error_response(
    request: HttpRequest | None,
    *,
    code: str,
    message: str,
    status: int,
    fields: dict[str, list[str]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    """Return a DRF response using the shared error contract."""
    return Response(
        build_error_payload(request, code=code, message=message, fields=fields),
        status=status,
        headers=dict(headers or {}),
    )


def api_json_error_response(
    request: HttpRequest,
    *,
    code: str,
    message: str,
    status: int,
    fields: dict[str, list[str]] | None = None,
) -> JsonResponse:
    """Return a Django JSON response for middleware-level failures."""
    response = JsonResponse(
        build_error_payload(request, code=code, message=message, fields=fields),
        status=status,
    )
    response["Cache-Control"] = "no-store"
    return response
