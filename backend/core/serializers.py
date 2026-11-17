"""Strict serializer defaults used by authentication and future write APIs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import ValidationError


class StrictSerializer(serializers.Serializer):
    """Reject unexpected input fields instead of silently ignoring them.

    Ignoring unknown fields makes role-escalation attempts easy to miss and
    hides client bugs. The policy is documented in docs/security.md.
    """

    def to_internal_value(self, data: Any) -> Any:
        if isinstance(data, Mapping):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise ValidationError(
                    {
                        "non_field_errors": [
                            "Unexpected field(s) supplied. Only documented fields are accepted."
                        ]
                    }
                )
        return super().to_internal_value(data)
