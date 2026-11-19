"""Strict serializer defaults used by authentication and write APIs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

UNEXPECTED_FIELDS_MESSAGE = "Unexpected field(s) supplied. Only documented fields are accepted."


class StrictFieldsMixin:
    """Reject unexpected input fields instead of silently ignoring them.

    Ignoring unknown fields makes role-escalation attempts easy to miss and
    hides client bugs. Shared by plain and ModelSerializer-based inputs so the
    same contract applies to every write endpoint.
    """

    fields: Any  # provided by DRF Serializer/ModelSerializer at runtime

    def to_internal_value(self, data: Any) -> Any:
        if isinstance(data, Mapping):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise ValidationError({"non_field_errors": [UNEXPECTED_FIELDS_MESSAGE]})
        return super().to_internal_value(data)  # type: ignore[misc]


class StrictSerializer(StrictFieldsMixin, serializers.Serializer):
    """Strict plain serializer base."""


class StrictModelSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    """Strict ModelSerializer base for catalog write endpoints."""
