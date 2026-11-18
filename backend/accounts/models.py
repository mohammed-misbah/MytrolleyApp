"""Accounts models: custom user, JWT sessions and database-backed throttling."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Application user with a unique email and explicit business permissions.

    Roles are represented by Django groups so authorization remains
    inspectable through Django's permission system.
    """

    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ["username"]
        permissions = [
            ("manage_users", "Can manage users and roles"),
            ("manage_catalog", "Can manage catalog data"),
        ]

    def __str__(self) -> str:
        return self.username


class LoginThrottle(models.Model):
    """Shared login-abuse counter keyed by an HMAC of username or client IP.

    Storing only keyed hashes avoids retaining raw usernames or IP addresses in
    this table while still allowing every application process to share state.
    """

    class Scope(models.TextChoices):
        USERNAME = "username", "Username"
        IP = "ip", "IP address"

    key_hash = models.CharField(max_length=64, unique=True)
    scope = models.CharField(max_length=16, choices=Scope.choices)
    failure_count = models.PositiveSmallIntegerField(default=0)
    window_started_at = models.DateTimeField(default=timezone.now)
    blocked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["blocked_until"], name="login_throttle_blocked_idx"),
            models.Index(fields=["scope", "updated_at"], name="login_throttle_scope_idx"),
        ]

    def __str__(self) -> str:
        return f"LoginThrottle({self.scope})"


class RefreshThrottle(models.Model):
    """Shared refresh-volume counter keyed by an HMAC of user ID or client IP.

    Storing only keyed hashes avoids retaining raw user IDs or IP addresses in
    this table while still allowing every application process to share state.
    """

    class Scope(models.TextChoices):
        USER = "user", "User"
        IP = "ip", "IP address"

    key_hash = models.CharField(max_length=64, unique=True)
    scope = models.CharField(max_length=16, choices=Scope.choices)
    hit_count = models.PositiveIntegerField(default=0)
    window_started_at = models.DateTimeField(default=timezone.now)
    blocked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["blocked_until"], name="refresh_throttle_block_idx"),
            models.Index(fields=["scope", "updated_at"], name="refresh_throttle_scope_idx"),
        ]

    def __str__(self) -> str:
        return f"RefreshThrottle({self.scope})"


class AuthSession(models.Model):
    """Server-side state for one authentication session.

    A session is created at login and tracks both the access token (via ``sid``)
    and the rotating refresh token (via ``refresh_jti``). The session belongs to
    a token family identified by ``family_id``; rotation creates a new
    ``refresh_jti`` within the same family. Reuse of an old refresh JTI revokes
    the entire family. Absolute session expiry is enforced by ``expires_at``.
    """

    class RevokeReason(models.TextChoices):
        LOGOUT = "logout", "Logout"
        LOGOUT_ALL = "logout_all", "Logout all sessions"
        PASSWORD_CHANGED = "password_changed", "Password changed"
        ACCOUNT_DEACTIVATED = "account_deactivated", "Account deactivated"
        ADMINISTRATIVE = "administrative", "Administrative revocation"
        REFRESH_REUSE = "refresh_reuse", "Refresh token reuse detected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auth_sessions",
    )
    family_id = models.UUIDField(default=uuid.uuid4, editable=False)
    refresh_jti = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(
        max_length=32,
        choices=RevokeReason.choices,
        blank=True,
    )
    user_agent = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="auth_session_user_idx"),
            models.Index(fields=["family_id"], name="auth_session_family_idx"),
            models.Index(fields=["expires_at"], name="auth_session_expires_idx"),
        ]

    def __str__(self) -> str:
        return f"AuthSession({self.user_id}, {self.id})"

    @property
    def is_active(self) -> bool:
        """Whether the session may still authenticate requests."""
        return self.revoked_at is None and self.expires_at > timezone.now()
