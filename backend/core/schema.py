"""Request/response schemas shared by API documentation and tests."""

from __future__ import annotations

from rest_framework import serializers


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
