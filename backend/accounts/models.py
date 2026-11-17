"""Accounts models: custom user and database-backed login throttling."""

from __future__ import annotations

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
