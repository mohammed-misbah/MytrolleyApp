"""Session-aware JWT authentication for every API request.

A syntactically valid access token is not enough. The ``sid`` claim must resolve
to an active ``AuthSession`` owned by the token's user. This makes logout,
password changes and account deactivation effective immediately instead of
waiting for the access token to expire. Refresh-type tokens are never accepted
because ``AUTH_TOKEN_CLASSES`` contains only the access-token class.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import Token

from accounts.models import AuthSession
from core.exceptions import SessionRevoked, TokenInvalid


class SessionAwareJWTAuthentication(JWTAuthentication):
    """Validate the Bearer token and its server-side session state."""

    www_authenticate_realm = "api"

    def get_user(self, validated_token: Token) -> Any:
        try:
            user = super().get_user(validated_token)
        except AuthenticationFailed as exc:
            # simplejwt rejects inactive users in its default rule. Distinguish
            # that from a forged/unknown-user token without leaking details.
            token_user_id = validated_token.get("user_id")
            user_model = get_user_model()
            if (
                token_user_id
                and user_model.objects.filter(
                    pk=token_user_id,
                    is_active=False,
                ).exists()
            ):
                raise SessionRevoked() from exc
            raise TokenInvalid() from exc

        session_id = validated_token.get("sid")
        if not session_id:
            raise TokenInvalid()

        try:
            session_id = uuid.UUID(str(session_id))
        except (TypeError, ValueError) as exc:
            raise TokenInvalid() from exc

        try:
            session = AuthSession.objects.get(pk=session_id)
        except AuthSession.DoesNotExist as exc:
            raise SessionRevoked() from exc

        if (
            session.user_id != user.pk
            or session.revoked_at is not None
            or session.expires_at <= timezone.now()
            or not user.is_active
        ):
            raise SessionRevoked()

        return user
