"""PostgreSQL-backed login abuse limits, cooldown and recovery."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from accounts.models import LoginThrottle
from tests.conftest import login, make_user, post_json

THROTTLE_SETTINGS = {
    "LOGIN_THROTTLE_USERNAME_LIMIT": 3,
    "LOGIN_THROTTLE_IP_LIMIT": 100,
    "LOGIN_THROTTLE_WINDOW_SECONDS": 900,
    "LOGIN_THROTTLE_COOLDOWN_SECONDS": 900,
}


def attempt(
    client: Client,
    username: str,
    password: str,
    *,
    ip: str = "127.0.0.1",
):
    # JWT login is header-credential based, so no CSRF token is involved.
    return post_json(
        client,
        "/api/v1/auth/login/",
        {"username": username, "password": password},
        REMOTE_ADDR=ip,
    )


@pytest.mark.django_db
@override_settings(**THROTTLE_SETTINGS)
def test_username_limit_blocks_then_recovers(client: Client, roles) -> None:
    make_user("throttled-user")

    for _ in range(3):
        response = attempt(client, "throttled-user", "wrong-password")
        assert response.status_code == 401

    blocked = attempt(client, "throttled-user", "Correct-Horse-42!")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    assert "throttled-user" not in blocked.content.decode()
    assert int(blocked["Retry-After"]) >= 1

    # Simulate cooldown expiry without sleeping.
    now = timezone.now()
    LoginThrottle.objects.update(
        blocked_until=now - timedelta(seconds=1),
        failure_count=0,
        window_started_at=now - timedelta(seconds=901),
    )

    recovered = attempt(client, "throttled-user", "Correct-Horse-42!")
    assert recovered.status_code == 200
    assert LoginThrottle.objects.count() == 0


@pytest.mark.django_db
@override_settings(
    LOGIN_THROTTLE_USERNAME_LIMIT=100,
    LOGIN_THROTTLE_IP_LIMIT=3,
    LOGIN_THROTTLE_WINDOW_SECONDS=900,
    LOGIN_THROTTLE_COOLDOWN_SECONDS=900,
)
def test_ip_limit_applies_across_usernames(client: Client, roles) -> None:
    make_user("ip-target")

    for index in range(3):
        response = attempt(
            client,
            f"unknown-{index}",
            "wrong-password",
            ip="203.0.113.50",
        )
        assert response.status_code == 401

    blocked = attempt(
        client,
        "ip-target",
        "Correct-Horse-42!",
        ip="203.0.113.50",
    )
    assert blocked.status_code == 429

    # A different source IP is unaffected.
    other_ip = attempt(
        client,
        "ip-target",
        "Correct-Horse-42!",
        ip="203.0.113.51",
    )
    assert other_ip.status_code == 200


@pytest.mark.django_db
@override_settings(**THROTTLE_SETTINGS)
def test_username_key_is_case_insensitive(client: Client, roles) -> None:
    make_user("case-user")

    for _ in range(3):
        assert attempt(client, "Case-User", "wrong-password").status_code == 401

    blocked = attempt(client, "case-user", "Correct-Horse-42!")
    assert blocked.status_code == 429


@pytest.mark.django_db
@override_settings(**THROTTLE_SETTINGS)
def test_shared_database_state_blocks_second_client(client: Client, roles) -> None:
    from django.test import Client as DjangoClient

    second_client = DjangoClient(enforce_csrf_checks=True)
    make_user("shared-user")

    for _ in range(3):
        assert attempt(client, "shared-user", "wrong-password").status_code == 401

    assert attempt(second_client, "shared-user", "Correct-Horse-42!").status_code == 429


@pytest.mark.django_db
@override_settings(**THROTTLE_SETTINGS)
def test_successful_login_clears_failure_counters(
    client: Client,
    roles,
) -> None:
    make_user("clear-user")

    assert attempt(client, "clear-user", "wrong-password").status_code == 401
    assert attempt(client, "clear-user", "wrong-password").status_code == 401
    assert LoginThrottle.objects.count() == 2

    assert login(client, "clear-user", "Correct-Horse-42!").status_code == 200
    assert LoginThrottle.objects.count() == 0


@pytest.mark.django_db
@override_settings(
    LOGIN_THROTTLE_USERNAME_LIMIT=2,
    LOGIN_THROTTLE_IP_LIMIT=100,
    LOGIN_THROTTLE_WINDOW_SECONDS=60,
    LOGIN_THROTTLE_COOLDOWN_SECONDS=60,
)
def test_failure_window_resets_after_expiry(client: Client, roles) -> None:
    make_user("window-user")

    assert attempt(client, "window-user", "wrong-password").status_code == 401
    assert attempt(client, "window-user", "wrong-password").status_code == 401
    assert attempt(client, "window-user", "Correct-Horse-42!").status_code == 429

    now = timezone.now()
    LoginThrottle.objects.update(
        failure_count=1,
        blocked_until=None,
        window_started_at=now - timedelta(seconds=61),
    )
    assert attempt(client, "window-user", "wrong-password").status_code == 401
    rows = LoginThrottle.objects.all()
    assert all(row.failure_count == 1 for row in rows)
