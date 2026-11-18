"""Attack-oriented JWT tests: revocation races, legacy tokens and input abuse."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Lock

import pytest
from django.db import close_old_connections
from django.test import Client, override_settings
from django.utils import timezone

from accounts.models import AuthSession, RefreshThrottle
from tests.conftest import access_token, login, logout, me, post_json, refresh, refresh_token


@pytest.mark.django_db(transaction=True)
def test_concurrent_logins_create_independent_sessions(administrator) -> None:
    """Two parallel logins each produce a usable token; neither is reused."""
    barrier = Barrier(2)
    results: list[int] = []
    results_lock = Lock()

    def worker() -> None:
        close_old_connections()
        worker_client = Client()
        try:
            barrier.wait(timeout=10)
            response = login(worker_client, "administrator", "Correct-Horse-42!")
            with results_lock:
                results.append(response.status_code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        for future in futures:
            future.result(timeout=30)

    assert results == [200, 200]
    assert AuthSession.objects.filter(user=administrator, revoked_at__isnull=True).count() == 2


@pytest.mark.django_db(transaction=True)
def test_concurrent_logout_revokes_every_session_once(administrator) -> None:
    """Two parallel logouts race on the same rows without corrupting state.

    Depending on timing, the second logout may itself be rejected with 401
    because the first one already revoked its token. Either way, no session
    may survive and no request may fail unexpectedly.
    """
    setup_client = Client()
    first_login = login(setup_client, "administrator", "Correct-Horse-42!")
    second_login = login(setup_client, "administrator", "Correct-Horse-42!")
    first_access = access_token(first_login)
    second_access = access_token(second_login)

    barrier = Barrier(2)
    statuses: list[int] = []
    results_lock = Lock()

    def worker(access: str) -> None:
        close_old_connections()
        worker_client = Client(enforce_csrf_checks=True)
        try:
            barrier.wait(timeout=10)
            response = logout(worker_client, access)
            with results_lock:
                statuses.append(response.status_code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker, first_access),
            pool.submit(worker, second_access),
        ]
        for future in futures:
            future.result(timeout=30)

    assert sorted(statuses) in ([200, 200], [200, 401])
    assert AuthSession.objects.filter(user=administrator, revoked_at__isnull=True).count() == 0
    assert (
        AuthSession.objects.filter(
            user=administrator,
            revoked_at__isnull=False,
            revoke_reason="logout_all",
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_legacy_refresh_token_cannot_authenticate_or_be_exchanged(
    client: Client,
    administrator,
) -> None:
    """A refresh token minted before the simplification is useless everywhere."""
    from rest_framework_simplejwt.tokens import RefreshToken

    legacy_refresh = str(RefreshToken.for_user(administrator))

    me_response = me(client, legacy_refresh)
    assert me_response.status_code == 401
    assert me_response.json()["error"]["code"] == "TOKEN_INVALID"

    refresh_response = post_json(
        client,
        "/api/v1/auth/refresh/",
        {"refresh": legacy_refresh},
    )
    assert refresh_response.status_code == 401
    assert refresh_response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    logout_response = client.post("/api/v1/auth/logout/")
    assert logout_response.status_code == 401
    assert AuthSession.objects.filter(user=administrator).count() == 0


@pytest.mark.django_db
def test_oversized_authorization_header_is_rejected(client: Client) -> None:
    response = client.get(
        "/api/v1/auth/me/",
        HTTP_AUTHORIZATION=f"Bearer {'x' * 5000}",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_INVALID"


@pytest.mark.django_db
def test_tampered_sid_claim_is_rejected(client: Client, administrator) -> None:
    """A token pointing at another user's session id must not authenticate."""
    import jwt as pyjwt
    from django.conf import settings
    from rest_framework_simplejwt.tokens import AccessToken

    attacker_token = AccessToken.for_user(administrator)
    attacker_token["sid"] = "00000000-0000-0000-0000-000000000000"
    # simplejwt injects aud/iss into the payload before signing; mirror that.
    forged = pyjwt.encode(
        {**attacker_token.payload, "aud": settings.JWT_AUDIENCE, "iss": settings.JWT_ISSUER},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256",
    )

    response = me(client, forged)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REVOKED"


@pytest.mark.django_db
def test_expired_session_row_cannot_be_revived_by_new_login(
    client: Client,
    administrator,
) -> None:
    """Each login creates a fresh session; the old expired row stays expired."""
    first_access = access_token(login(client, "administrator", "Correct-Horse-42!"))
    old_session = AuthSession.objects.get(user=administrator)
    old_session.expires_at = timezone.now() - timedelta(days=1)
    old_session.save(update_fields=["expires_at"])

    login(client, "administrator", "Correct-Horse-42!")

    old_session.refresh_from_db()
    assert old_session.revoked_at is None  # never re-activated or reused
    assert me(client, first_access).status_code == 401
    assert AuthSession.objects.filter(user=administrator).count() == 2


@pytest.mark.django_db
def test_sql_injection_attempt_is_a_generic_login_failure(
    client: Client,
    administrator,
) -> None:
    response = login(client, "administrator' OR 1=1 --", "anything")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    text = response.content.decode().lower()
    for leak in ("sql", "syntax", "psycopg", "traceback"):
        assert leak not in text


@pytest.mark.django_db
def test_xss_payload_is_not_reflected_as_html(client: Client, roles) -> None:
    payload = "<script>alert(1)</script>"
    response = login(client, payload, "anything")

    assert response.status_code == 401
    assert response["Content-Type"].startswith("application/json")
    assert payload not in response.content.decode()


@pytest.mark.django_db
def test_no_permissive_cors_headers(client: Client) -> None:
    response = client.get(
        "/api/v1/health/live/",
        HTTP_ORIGIN="https://attacker.example",
    )

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response
    assert "Access-Control-Allow-Credentials" not in response


@pytest.mark.django_db
@override_settings(
    REFRESH_THROTTLE_USER_LIMIT=2,
    REFRESH_THROTTLE_IP_LIMIT=1000,
    REFRESH_THROTTLE_WINDOW_SECONDS=900,
    REFRESH_THROTTLE_COOLDOWN_SECONDS=900,
)
def test_refresh_volume_is_rate_limited(client: Client, administrator) -> None:
    login_resp = login(client, "administrator", "Correct-Horse-42!")
    token = refresh_token(login_resp)

    first = refresh(client, token)
    assert first.status_code == 200
    second = refresh(client, refresh_token(first))
    assert second.status_code == 200

    blocked = refresh(client, refresh_token(second))
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    assert int(blocked["Retry-After"]) >= 1
    assert RefreshThrottle.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_refresh_consumes_token_once(administrator) -> None:
    setup_client = Client()
    token = refresh_token(login(setup_client, "administrator", "Correct-Horse-42!"))
    barrier = Barrier(2)
    results: list[int] = []
    results_lock = Lock()

    def worker() -> None:
        close_old_connections()
        worker_client = Client()
        try:
            barrier.wait(timeout=10)
            response = refresh(worker_client, token)
            with results_lock:
                results.append(response.status_code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        for future in futures:
            future.result(timeout=30)

    assert sorted(results) == [200, 401]
    # Reuse detection revokes the family, including the one successful pair.
    session = AuthSession.objects.get(user=administrator)
    assert session.revoked_at is not None
    assert session.revoke_reason == "refresh_reuse"


@pytest.mark.django_db
def test_oversized_refresh_token_is_rejected(client: Client, administrator) -> None:
    login(client, "administrator", "Correct-Horse-42!")

    response = post_json(
        client,
        "/api/v1/auth/refresh/",
        {"refresh": "x" * 5000},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "refresh" in response.json()["error"]["fields"]
