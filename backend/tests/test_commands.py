"""Management commands for roles, initial admin and throttle pruning."""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from accounts.models import AuthSession, LoginThrottle, RefreshThrottle
from accounts.roles import ROLE_ADMINISTRATOR, ROLE_DATA_ENTRY

User = get_user_model()
STRONG_PASSWORD = "Strong-Admin-Pass-99!"


@pytest.mark.django_db
def test_seed_roles_command_is_idempotent() -> None:
    out = StringIO()
    call_command("seed_roles", stdout=out)
    call_command("seed_roles", stdout=out)

    assert Group.objects.filter(name=ROLE_ADMINISTRATOR).count() == 1
    assert Group.objects.filter(name=ROLE_DATA_ENTRY).count() == 1
    assert "Roles are up to date." in out.getvalue()


@pytest.mark.django_db
def test_no_default_account_is_created_by_migrations() -> None:
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_create_initial_admin_interactively(monkeypatch) -> None:
    passwords = iter([STRONG_PASSWORD, STRONG_PASSWORD])
    monkeypatch.setattr(
        "accounts.management.commands.create_initial_admin.getpass.getpass",
        lambda _prompt: next(passwords),
    )
    out = StringIO()

    call_command(
        "create_initial_admin",
        username="root-admin",
        email="root@example.test",
        stdout=out,
    )

    user = User.objects.get(username="root-admin")
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.check_password(STRONG_PASSWORD)
    assert list(user.groups.values_list("name", flat=True)) == [ROLE_ADMINISTRATOR]
    assert STRONG_PASSWORD not in out.getvalue()


@pytest.mark.django_db
def test_create_initial_admin_rejects_mismatched_passwords(monkeypatch) -> None:
    passwords = iter([STRONG_PASSWORD, "Different-Pass-99!"])
    monkeypatch.setattr(
        "accounts.management.commands.create_initial_admin.getpass.getpass",
        lambda _prompt: next(passwords),
    )

    with pytest.raises(CommandError, match="do not match"):
        call_command(
            "create_initial_admin",
            username="mismatch-admin",
            email="mismatch@example.test",
            stdout=StringIO(),
        )
    assert not User.objects.filter(username="mismatch-admin").exists()


@pytest.mark.django_db
def test_create_initial_admin_rejects_weak_password(monkeypatch) -> None:
    passwords = iter(["short", "short"])
    monkeypatch.setattr(
        "accounts.management.commands.create_initial_admin.getpass.getpass",
        lambda _prompt: next(passwords),
    )

    with pytest.raises(CommandError, match="Password rejected"):
        call_command(
            "create_initial_admin",
            username="weak-admin",
            email="weak@example.test",
            stdout=StringIO(),
        )
    assert not User.objects.filter(username="weak-admin").exists()


@pytest.mark.django_db
def test_create_initial_admin_refuses_duplicate(monkeypatch, administrator) -> None:
    passwords = iter([STRONG_PASSWORD, STRONG_PASSWORD])
    monkeypatch.setattr(
        "accounts.management.commands.create_initial_admin.getpass.getpass",
        lambda _prompt: next(passwords),
    )

    with pytest.raises(CommandError, match="already exists"):
        call_command(
            "create_initial_admin",
            username="administrator",
            email="another@example.test",
            stdout=StringIO(),
        )


@pytest.mark.django_db
def test_prune_login_throttles_removes_only_stale_rows() -> None:
    now = timezone.now()
    stale = LoginThrottle.objects.create(
        key_hash="a" * 64,
        scope=LoginThrottle.Scope.IP,
        failure_count=1,
        window_started_at=now - timedelta(days=10),
        blocked_until=None,
    )
    LoginThrottle.objects.filter(pk=stale.pk).update(updated_at=now - timedelta(days=10))
    active = LoginThrottle.objects.create(
        key_hash="b" * 64,
        scope=LoginThrottle.Scope.USERNAME,
        failure_count=10,
        window_started_at=now,
        blocked_until=now + timedelta(minutes=10),
    )

    call_command("prune_login_throttles", days=7, stdout=StringIO())

    assert not LoginThrottle.objects.filter(pk=stale.pk).exists()
    assert LoginThrottle.objects.filter(pk=active.pk).exists()


@pytest.mark.django_db
def test_prune_jwt_tokens_removes_only_sessions_expired_beyond_retention(
    administrator,
) -> None:
    now = timezone.now()
    stale = AuthSession.objects.create(
        user=administrator,
        refresh_jti="stale-jti",
        expires_at=now - timedelta(days=10),
    )
    recent = AuthSession.objects.create(
        user=administrator,
        refresh_jti="recent-jti",
        expires_at=now + timedelta(days=1),
    )
    stale_throttle = RefreshThrottle.objects.create(
        key_hash="c" * 64,
        scope=RefreshThrottle.Scope.IP,
        hit_count=1,
        window_started_at=now - timedelta(days=10),
        blocked_until=None,
    )
    RefreshThrottle.objects.filter(pk=stale_throttle.pk).update(updated_at=now - timedelta(days=10))
    active_throttle = RefreshThrottle.objects.create(
        key_hash="d" * 64,
        scope=RefreshThrottle.Scope.USER,
        hit_count=5,
        window_started_at=now,
        blocked_until=now + timedelta(minutes=10),
    )

    out = StringIO()
    call_command("prune_jwt_tokens", days=7, stdout=out)

    assert not AuthSession.objects.filter(pk=stale.pk).exists()
    assert AuthSession.objects.filter(pk=recent.pk).exists()
    assert not RefreshThrottle.objects.filter(pk=stale_throttle.pk).exists()
    assert RefreshThrottle.objects.filter(pk=active_throttle.pk).exists()
    assert "Pruned 1 expired sessions and 1 stale refresh throttle rows." in out.getvalue()


@pytest.mark.django_db
def test_prune_jwt_tokens_rejects_invalid_retention() -> None:
    with pytest.raises(CommandError, match="at least one day"):
        call_command("prune_jwt_tokens", days=0, stdout=StringIO())
