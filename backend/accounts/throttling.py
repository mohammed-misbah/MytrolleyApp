"""PostgreSQL-backed login abuse protection shared by all processes."""

from __future__ import annotations

import hashlib
import hmac
import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import LoginThrottle, RefreshThrottle

_HASH_CONTEXT = b"mytrolley-login-throttle-v1:"


@dataclass(frozen=True, slots=True)
class ThrottleDecision:
    """Whether an attempt may proceed and, if not, how long to wait."""

    allowed: bool
    retry_after_seconds: int = 0


def _hash_key(scope: str, value: str) -> str:
    """Keyed hash so throttle rows do not retain raw usernames or IPs."""
    message = _HASH_CONTEXT + scope.encode("utf-8") + b":" + value.encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _keys(username: str, client_ip: str) -> list[tuple[str, str, str]]:
    """Build (scope, display value, key hash) tuples for applicable limits."""
    normalized_username = username.strip().casefold()
    keys: list[tuple[str, str, str]] = []
    if normalized_username:
        keys.append(
            (
                LoginThrottle.Scope.USERNAME,
                normalized_username,
                _hash_key(LoginThrottle.Scope.USERNAME, normalized_username),
            )
        )
    if client_ip and client_ip != "unknown":
        keys.append(
            (
                LoginThrottle.Scope.IP,
                client_ip,
                _hash_key(LoginThrottle.Scope.IP, client_ip),
            )
        )
    return keys


def _limit_for(scope: str) -> int:
    if scope == LoginThrottle.Scope.USERNAME:
        return settings.LOGIN_THROTTLE_USERNAME_LIMIT
    return settings.LOGIN_THROTTLE_IP_LIMIT


def _retry_after(blocked_until: datetime, now: datetime) -> int:
    return max(1, math.ceil((blocked_until - now).total_seconds()))


def check_login_throttle(
    username: str,
    client_ip: str,
    *,
    now: datetime | None = None,
) -> ThrottleDecision:
    """Check both username and IP counters without writing on read."""
    current = now or timezone.now()
    keys = _keys(username, client_ip)
    if not keys:
        return ThrottleDecision(allowed=True)

    rows = LoginThrottle.objects.filter(key_hash__in=[key_hash for _, _, key_hash in keys])
    retry_after = 0
    blocked = False
    for row in rows:
        if row.blocked_until and row.blocked_until > current:
            blocked = True
            retry_after = max(retry_after, _retry_after(row.blocked_until, current))
        elif row.blocked_until is None:
            window_age = current - row.window_started_at
            if window_age < timedelta(
                seconds=settings.LOGIN_THROTTLE_WINDOW_SECONDS
            ) and row.failure_count >= _limit_for(row.scope):
                # Defensive fallback for a row that reached the threshold but
                # lost its blocked_until value (for example manual data edits).
                blocked = True
                retry_after = max(retry_after, 1)
    return ThrottleDecision(allowed=not blocked, retry_after_seconds=retry_after)


def record_login_failure(
    username: str,
    client_ip: str,
    *,
    now: datetime | None = None,
) -> ThrottleDecision:
    """Atomically increment counters and start a cooldown at the threshold."""
    current = now or timezone.now()
    keys = _keys(username, client_ip)
    if not keys:
        return ThrottleDecision(allowed=True)

    retry_after = 0
    with transaction.atomic():
        for scope, _value, key_hash in keys:
            row, _created = LoginThrottle.objects.get_or_create(
                key_hash=key_hash,
                defaults={
                    "scope": scope,
                    "failure_count": 0,
                    "window_started_at": current,
                },
            )
            # Serialize concurrent failures for the same key across processes.
            row = LoginThrottle.objects.select_for_update().get(pk=row.pk)

            if row.blocked_until and row.blocked_until > current:
                retry_after = max(
                    retry_after,
                    _retry_after(row.blocked_until, current),
                )
                continue

            window = timedelta(seconds=settings.LOGIN_THROTTLE_WINDOW_SECONDS)
            if row.blocked_until or current - row.window_started_at >= window:
                row.failure_count = 0
                row.blocked_until = None
                row.window_started_at = current

            row.failure_count += 1
            if row.failure_count >= _limit_for(scope):
                row.blocked_until = current + timedelta(
                    seconds=settings.LOGIN_THROTTLE_COOLDOWN_SECONDS
                )
                retry_after = max(
                    retry_after,
                    settings.LOGIN_THROTTLE_COOLDOWN_SECONDS,
                )
            row.save(
                update_fields=[
                    "failure_count",
                    "window_started_at",
                    "blocked_until",
                    "updated_at",
                ]
            )

    return ThrottleDecision(
        allowed=retry_after == 0,
        retry_after_seconds=retry_after,
    )


def clear_login_throttle(username: str, client_ip: str) -> None:
    """Clear counters after a successful login, allowing automatic recovery."""
    keys = _keys(username, client_ip)
    if keys:
        LoginThrottle.objects.filter(key_hash__in=[key_hash for _, _, key_hash in keys]).delete()


_REFRESH_HASH_CONTEXT = b"mytrolley-refresh-throttle-v1:"


def _refresh_hash_key(scope: str, value: str) -> str:
    """Keyed hash so throttle rows do not retain raw user IDs or IPs."""
    message = _REFRESH_HASH_CONTEXT + scope.encode("utf-8") + b":" + value.encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _refresh_keys(user_id: int | None, client_ip: str) -> list[tuple[str, str]]:
    """Build (scope, key hash) pairs for the applicable refresh limits."""
    keys: list[tuple[str, str]] = []
    if user_id is not None:
        value = f"user:{user_id}"
        keys.append(
            (
                RefreshThrottle.Scope.USER,
                _refresh_hash_key(RefreshThrottle.Scope.USER, value),
            )
        )
    if client_ip and client_ip != "unknown":
        keys.append(
            (
                RefreshThrottle.Scope.IP,
                _refresh_hash_key(RefreshThrottle.Scope.IP, client_ip),
            )
        )
    return keys


def _refresh_limit_for(scope: str) -> int:
    if scope == RefreshThrottle.Scope.USER:
        return settings.REFRESH_THROTTLE_USER_LIMIT
    return settings.REFRESH_THROTTLE_IP_LIMIT


def check_refresh_throttle(
    user_id: int | None,
    client_ip: str,
    *,
    now: datetime | None = None,
) -> ThrottleDecision:
    """Count one refresh attempt and block abusive volumes.

    Unlike the login counter, every refresh attempt is counted because the
    threat is request volume against a valid or stolen token. Counters reset
    when the window expires; a blocked key waits for the cooldown.
    """
    current = now or timezone.now()
    keys = _refresh_keys(user_id, client_ip)
    if not keys:
        return ThrottleDecision(allowed=True)

    retry_after = 0
    blocked = False
    with transaction.atomic():
        for scope, key_hash in keys:
            row, _created = RefreshThrottle.objects.get_or_create(
                key_hash=key_hash,
                defaults={
                    "scope": scope,
                    "hit_count": 0,
                    "window_started_at": current,
                },
            )
            row = RefreshThrottle.objects.select_for_update().get(pk=row.pk)

            if row.blocked_until and row.blocked_until > current:
                blocked = True
                retry_after = max(retry_after, _retry_after(row.blocked_until, current))
                continue

            window = timedelta(seconds=settings.REFRESH_THROTTLE_WINDOW_SECONDS)
            if row.blocked_until or current - row.window_started_at >= window:
                row.hit_count = 0
                row.blocked_until = None
                row.window_started_at = current

            row.hit_count += 1
            # Unlike a failure counter, the hit is recorded before the request
            # proceeds. Allow exactly ``limit`` refreshes per window.
            if row.hit_count > _refresh_limit_for(scope):
                row.blocked_until = current + timedelta(
                    seconds=settings.REFRESH_THROTTLE_COOLDOWN_SECONDS
                )
                retry_after = max(
                    retry_after,
                    settings.REFRESH_THROTTLE_COOLDOWN_SECONDS,
                )
                blocked = True
            row.save(
                update_fields=[
                    "hit_count",
                    "window_started_at",
                    "blocked_until",
                    "updated_at",
                ]
            )

    return ThrottleDecision(allowed=not blocked, retry_after_seconds=retry_after)


def clear_refresh_throttle(user_id: int, client_ip: str) -> None:
    """Clear refresh counters after a successful interactive login."""
    keys = _refresh_keys(user_id, client_ip)
    if keys:
        RefreshThrottle.objects.filter(key_hash__in=[key_hash for _, key_hash in keys]).delete()
