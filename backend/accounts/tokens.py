"""JWT issuance, rotation, reuse detection and revocation services.

All state-changing operations use PostgreSQL transactions. Refresh rotation
locks the ``AuthSession`` row so two requests cannot consume the same refresh
token concurrently. Access tokens are never trusted on their own: the custom
authentication class resolves the ``sid`` claim against this table.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import AuthSession
from core.exceptions import RefreshReuseDetected, SessionRevoked
from core.security import get_client_ip

_auth_logger = logging.getLogger("mytrolley.auth")


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    """Serializable token pair plus non-secret metadata."""

    access: str
    access_expires_in: int
    refresh: str
    refresh_expires_in: int
    session_id: uuid.UUID
    family_id: uuid.UUID


def _request_metadata(request: Any) -> tuple[str, str | None]:
    """Return bounded user-agent text and a validated client IP."""
    user_agent = str(request.META.get("HTTP_USER_AGENT", ""))[:255]
    client_ip = get_client_ip(request)
    return user_agent, (client_ip if client_ip != "unknown" else None)


def create_auth_session(user: Any, request: Any) -> IssuedTokens:
    """Create one login session and issue an access/refresh token pair.

    The session row stores the initial refresh JTI and family ID. Access and
    refresh lifetimes come from settings. Rotation is bounded by the absolute
    session expiry.
    """
    now = timezone.now()
    access_lifetime = timedelta(seconds=settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS)
    absolute_lifetime = timedelta(seconds=settings.JWT_ABSOLUTE_SESSION_SECONDS)
    # The refresh token never outlives the absolute session limit.
    refresh_lifetime = min(
        timedelta(seconds=settings.JWT_REFRESH_TOKEN_LIFETIME_SECONDS),
        absolute_lifetime,
    )
    absolute_expiry = now + absolute_lifetime
    session_id = uuid.uuid4()
    family_id = uuid.uuid4()
    user_agent, client_ip = _request_metadata(request)

    with transaction.atomic():
        access = AccessToken.for_user(user)
        access["sid"] = str(session_id)
        access.set_exp(from_time=now, lifetime=access_lifetime)

        refresh = RefreshToken.for_user(user)
        refresh.set_jti()
        # The family claim lets the API revoke exactly the compromised family
        # when a token is presented after its JTI was rotated away.
        refresh["fam"] = str(family_id)
        refresh_jti: str = refresh[settings.SIMPLE_JWT["JTI_CLAIM"]]  # type: ignore[index]
        refresh.set_exp(from_time=now, lifetime=refresh_lifetime)

        AuthSession.objects.create(
            id=session_id,
            user=user,
            family_id=family_id,
            refresh_jti=refresh_jti,
            expires_at=absolute_expiry,
            user_agent=user_agent,
            ip_address=client_ip,
        )

    return IssuedTokens(
        access=str(access),
        access_expires_in=max(1, int(access_lifetime.total_seconds())),
        refresh=str(refresh),
        refresh_expires_in=max(1, int(refresh_lifetime.total_seconds())),
        session_id=session_id,
        family_id=family_id,
    )


def rotate_refresh_token(
    session: AuthSession,
    token: RefreshToken,
    *,
    request: Any,
) -> IssuedTokens:
    """Rotate the refresh token for an existing session.

    The session row is locked. If the supplied refresh JTI does not match the
    stored one, the entire token family is revoked as a reuse attack.
    """
    now = timezone.now()
    access_lifetime = timedelta(seconds=settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS)
    jti_claim: str = settings.SIMPLE_JWT["JTI_CLAIM"]  # type: ignore[assignment]

    with transaction.atomic():
        locked_session = AuthSession.objects.select_for_update().get(pk=session.pk)

        if locked_session.revoked_at is not None or locked_session.expires_at <= now:
            raise SessionRevoked("Session revoked or expired.")
        if not locked_session.user.is_active:
            raise SessionRevoked("User account is inactive.")

        supplied_jti: str = token.get(jti_claim)
        if supplied_jti != locked_session.refresh_jti:
            # Capture family_id before raising, so the view can revoke the family
            family_id = locked_session.family_id
            # Do not mark as revoked here; the transaction will be rolled back.
            # The view will handle revocation in a separate transaction.
            raise RefreshReuseDetected(family_id=family_id)

        new_jti = uuid.uuid4().hex
        # A rotated refresh token must never extend past the absolute session limit.
        refresh_lifetime = min(
            timedelta(seconds=settings.JWT_REFRESH_TOKEN_LIFETIME_SECONDS),
            locked_session.expires_at - now,
        )

        access = AccessToken.for_user(locked_session.user)
        access["sid"] = str(locked_session.id)
        access.set_exp(from_time=now, lifetime=access_lifetime)

        refresh = RefreshToken.for_user(locked_session.user)
        refresh[jti_claim] = new_jti
        refresh["fam"] = str(locked_session.family_id)
        refresh.set_exp(from_time=now, lifetime=refresh_lifetime)

        locked_session.refresh_jti = new_jti
        locked_session.last_used_at = now
        locked_session.save(update_fields=["refresh_jti", "last_used_at", "updated_at"])

    return IssuedTokens(
        access=str(access),
        access_expires_in=max(1, int(access_lifetime.total_seconds())),
        refresh=str(refresh),
        refresh_expires_in=max(1, int(refresh_lifetime.total_seconds())),
        session_id=locked_session.id,
        family_id=locked_session.family_id,
    )


def _revoke_family_outside_transaction(family_id: uuid.UUID, now: Any, reason: str) -> int:
    """Revoke all sessions sharing the given family ID in a new transaction."""
    revoked = 0
    with transaction.atomic():
        for session in AuthSession.objects.select_for_update().filter(
            family_id=family_id, revoked_at__isnull=True
        ):
            session.revoked_at = now
            session.revoke_reason = reason
            session.save(update_fields=["revoked_at", "revoke_reason"])
            revoked += 1
    return revoked


def revoke_user_sessions(user_id: int, *, reason: str) -> int:
    """Revoke every active session belonging to exactly one user.

    Rows are locked so concurrent logouts or a concurrent password change do
    not race. Other users' sessions are never touched because the query is
    scoped by ``user_id``.
    """
    now = timezone.now()
    revoked = 0
    with transaction.atomic():
        sessions = list(
            AuthSession.objects.select_for_update().filter(
                user_id=user_id,
                revoked_at__isnull=True,
            )
        )
        for session in sessions:
            session.revoked_at = now
            session.revoke_reason = reason
            session.save(update_fields=["revoked_at", "revoke_reason"])
            revoked += 1
    return revoked
