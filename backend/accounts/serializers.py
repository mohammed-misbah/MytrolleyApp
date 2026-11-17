"""Authentication and account serializers with explicit public fields."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.roles import BUSINESS_PERMISSIONS
from core.serializers import StrictSerializer

User = get_user_model()


class LoginSerializer(StrictSerializer):
    """Validated login input. Unknown fields are rejected, not ignored."""

    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(
        max_length=128,
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )


class UserSerializer(serializers.Serializer):
    """Read-only response contract for the current user.

    No user list or sensitive account fields (password, permissions beyond the
    business set, session identifiers) are exposed.
    """

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    is_staff = serializers.BooleanField(read_only=True)
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    def get_roles(self, obj: Any) -> list[str]:
        return sorted(group.name for group in obj.groups.all())

    def get_permissions(self, obj: Any) -> list[str]:
        return sorted(permission for permission in BUSINESS_PERMISSIONS if obj.has_perm(permission))


class CsrfBootstrapSerializer(serializers.Serializer):
    """CSRF bootstrap response."""

    csrfToken = serializers.CharField(read_only=True)
