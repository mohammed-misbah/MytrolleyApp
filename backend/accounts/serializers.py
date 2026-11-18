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


class RefreshRequestSerializer(StrictSerializer):
    """Refresh input. API clients may send the refresh token in the body.

    Browsers do not need this body: the refresh token is read from the
    HttpOnly ``refresh_token`` cookie, and that request must also send
    ``X-CSRFToken``.
    """

    refresh = serializers.CharField(
        max_length=4096,
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
        required=False,  # Can come from the HttpOnly cookie instead
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


class LoginResponseSerializer(serializers.Serializer):
    """Access token and safe profile returned by login and refresh.

    The refresh token is deliberately absent: browsers receive it only as an
    HttpOnly cookie, and non-browser clients are documented in
    ``docs/frontend-integration.md``.
    """

    access = serializers.CharField(read_only=True)
    token_type = serializers.CharField(read_only=True)
    expires_in = serializers.IntegerField(
        read_only=True,
        help_text="Access-token lifetime in seconds. Use the refresh cookie to obtain a new one.",
    )
    refresh_expires_in = serializers.IntegerField(
        read_only=True,
        help_text=(
            "Refresh-token lifetime in seconds, capped by the absolute session "
            "limit. The token itself is only sent as an HttpOnly cookie."
        ),
    )
    user = UserSerializer(read_only=True)


class LogoutResponseSerializer(serializers.Serializer):
    """Body returned after every session for the caller has been revoked."""

    message = serializers.CharField(read_only=True)
