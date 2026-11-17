"""Request/response schemas shared by API documentation and tests."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter
from rest_framework import serializers

from core.context import REQUEST_ID_HEADER


class ErrorBodySerializer(serializers.Serializer):
    """Machine-readable error details."""

    code = serializers.CharField(help_text="Stable machine-readable error code.")
    message = serializers.CharField(help_text="Safe human-readable message.")
    fields = serializers.DictField(  # type: ignore[assignment]  # documented contract name
        child=serializers.ListField(child=serializers.CharField()),
        help_text="Field-specific validation messages, or an empty object.",
    )
    request_id = serializers.CharField(help_text="Request ID for support correlation.")


class ErrorEnvelopeSerializer(serializers.Serializer):
    """The single error contract returned by every API error."""

    error = ErrorBodySerializer()


CSRF_HEADER_PARAMETER = OpenApiParameter(
    name="X-CSRFToken",
    type=str,
    location=OpenApiParameter.HEADER,
    required=True,
    description=(
        "CSRF token for the request. Use the masked token returned by "
        "GET /api/v1/auth/csrf/ or the value of the csrftoken cookie; both "
        "are accepted and they are not expected to be identical. Required "
        "for login, logout and every authenticated unsafe request."
    ),
)

REQUEST_ID_RESPONSE_PARAMETER = OpenApiParameter(
    name=REQUEST_ID_HEADER,
    type=str,
    location=OpenApiParameter.HEADER,
    required=False,
    description="Echoed request identifier (generated when absent/invalid).",
)
