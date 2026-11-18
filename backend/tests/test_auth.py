"""JWT authentication tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import AuthSession
from accounts.roles import ROLE_ADMINISTRATOR
from tests.conftest import (
    access_token,
    auth_header,
    csrf_token,
    login,
    logout,
    make_user,
    me,
    post_json,
    refresh,
    refresh_token,
)


def _decoded(token: str) -> dict:
    return jwt.decode(
        token,
        settings.JWT_SIGNING_KEY,
        algorithms=["HS256"],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
    )


@pytest.mark.django_db
def test_login_returns_access_token_and_safe_user(
    client: Client,
    administrator,
) -> None:
    response = login(client, "administrator", "Correct-Horse-42!")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS
    assert body["refresh_expires_in"] == settings.JWT_REFRESH_TOKEN_LIFETIME_SECONDS
    assert body["access"]
    assert "refresh" not in body
    assert body["user"]["username"] == "administrator"
    assert body["user"]["roles"] == [ROLE_ADMINISTRATOR]
    assert body["user"]["is_staff"] is True
    assert "accounts.manage_users" in body["user"]["permissions"]
    for forbidden in ("password", "last_login", "session", "user_permissions"):
        assert forbidden not in body
        assert forbidden not in body["user"]
    assert response["Cache-Control"] == "no-store"
    # The JWT API must not create a Django session.
    assert "sessionid" not in response.cookies
    assert AuthSession.objects.filter(user=administrator).count() == 1
    # The refresh token travels only as an HttpOnly cookie, never in JSON.
    assert "refresh_token" in response.cookies
    cookie = response.cookies["refresh_token"]
    assert cookie["httponly"] is True
    assert cookie["path"] == "/api/v1/auth/"
    assert cookie["samesite"] == ("Lax" if settings.DEBUG else "Strict")
    assert bool(cookie["secure"]) is (not settings.DEBUG)
    assert cookie["max-age"] == settings.JWT_REFRESH_TOKEN_LIFETIME_SECONDS


@pytest.mark.django_db
def test_access_token_claims_and_lifetime(client: Client, administrator) -> None:
    response = login(client, "administrator", "Correct-Horse-42!")
    claims = _decoded(access_token(response))
    session = AuthSession.objects.get(user=administrator)

    assert claims["token_type"] == "access"
    assert int(claims["user_id"]) == administrator.pk
    assert claims["sid"] == str(session.id)
    assert claims["iss"] == settings.JWT_ISSUER
    assert claims["aud"] == settings.JWT_AUDIENCE
    assert claims["exp"] - claims["iat"] == settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS
    assert session.expires_at > timezone.now() + timedelta(
        seconds=settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS - 10
    )


@pytest.mark.django_db
def test_jwt_login_does_not_require_csrf(client: Client, administrator) -> None:
    # The fixture enforces CSRF for every request; no cookie or header is sent.
    response = login(client, "administrator", "Correct-Horse-42!")

    assert response.status_code == 200
    # Login issues the readable CSRF cookie a browser needs for cookie refresh.
    assert "csrftoken" in response.cookies
    assert response.cookies["csrftoken"]["httponly"] in ("", None)
    # The refresh cookie stays HttpOnly.
    assert response.cookies["refresh_token"]["httponly"] is True


@pytest.mark.django_db
def test_login_failures_are_generic_for_wrong_unknown_and_inactive(
    client: Client,
    roles,
) -> None:
    make_user("active-user")
    make_user("inactive-user", is_active=False)

    wrong = login(client, "active-user", "wrong-password")
    unknown = login(client, "missing-user", "wrong-password")
    inactive = login(client, "inactive-user", "Correct-Horse-42!")

    assert wrong.status_code == unknown.status_code == inactive.status_code == 401
    for response in (wrong, unknown, inactive):
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
        assert response.json()["error"]["message"] == "Invalid username or password."
        assert response.json()["error"]["fields"] == {}
        assert "active-user" not in response.content.decode()
        assert "inactive-user" not in response.content.decode()
        assert "wrong-password" not in response.content.decode()
        assert response["WWW-Authenticate"] == "Bearer"


@pytest.mark.django_db
def test_login_validates_missing_and_unknown_fields(client: Client, administrator) -> None:
    missing = post_json(client, "/api/v1/auth/login/", {})
    unknown = post_json(
        client,
        "/api/v1/auth/login/",
        {
            "username": "administrator",
            "password": "Correct-Horse-42!",
            "is_staff": True,
            "permissions": ["accounts.manage_users"],
        },
    )

    assert missing.status_code == 400
    assert set(missing.json()["error"]["fields"]) >= {"username", "password"}
    assert unknown.status_code == 400
    assert "non_field_errors" in unknown.json()["error"]["fields"]


@pytest.mark.django_db
def test_me_requires_a_valid_access_token(client: Client, administrator) -> None:
    login_response = login(client, "administrator", "Correct-Horse-42!")
    access = access_token(login_response)

    anonymous = client.get("/api/v1/auth/me/")
    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "UNAUTHENTICATED"
    assert anonymous["WWW-Authenticate"] == "Bearer"

    valid = me(client, access)
    assert valid.status_code == 200
    assert valid.json()["username"] == "administrator"

    # Refresh-type tokens are rejected even if one is minted directly.
    legacy_refresh = str(RefreshToken.for_user(administrator))
    wrong_type = client.get("/api/v1/auth/me/", **auth_header(legacy_refresh))
    assert wrong_type.status_code == 401
    assert wrong_type.json()["error"]["code"] == "TOKEN_INVALID"

    tampered = access[:-3] + ("aaa" if not access.endswith("aaa") else "bbb")
    tampered_response = client.get("/api/v1/auth/me/", **auth_header(tampered))
    assert tampered_response.status_code == 401
    assert tampered_response.json()["error"]["code"] == "TOKEN_INVALID"

    malformed = client.get(
        "/api/v1/auth/me/",
        HTTP_AUTHORIZATION="Bearer not-a-token",
    )
    assert malformed.status_code == 401
    assert malformed.json()["error"]["code"] == "TOKEN_INVALID"


@pytest.mark.django_db
def test_expired_and_foreign_signature_access_tokens_are_rejected(
    client: Client,
    administrator,
) -> None:
    login_response = login(client, "administrator", "Correct-Horse-42!")
    claims = _decoded(access_token(login_response))
    now = datetime.now(tz=UTC)

    expired_payload = {
        **claims,
        "iat": now - timedelta(minutes=10),
        "exp": now - timedelta(minutes=5),
        "jti": uuid.uuid4().hex,
    }
    expired = jwt.encode(expired_payload, settings.JWT_SIGNING_KEY, algorithm="HS256")
    expired_response = client.get("/api/v1/auth/me/", **auth_header(expired))
    assert expired_response.status_code == 401
    assert expired_response.json()["error"]["code"] == "TOKEN_INVALID"

    foreign = jwt.encode(expired_payload, "x" * 64, algorithm="HS256")
    foreign_response = client.get("/api/v1/auth/me/", **auth_header(foreign))
    assert foreign_response.status_code == 401
    assert foreign_response.json()["error"]["code"] == "TOKEN_INVALID"


@pytest.mark.django_db
def test_access_token_without_session_is_rejected(client: Client, administrator) -> None:
    login_response = login(client, "administrator", "Correct-Horse-42!")
    access = access_token(login_response)
    AuthSession.objects.filter(user=administrator).delete()

    response = me(client, access)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REVOKED"


@pytest.mark.django_db
def test_session_expiry_revokes_access_token(client: Client, administrator) -> None:
    access = access_token(login(client, "administrator", "Correct-Horse-42!"))
    session = AuthSession.objects.get(user=administrator)
    session.expires_at = timezone.now() - timedelta(seconds=1)
    session.save(update_fields=["expires_at"])

    response = me(client, access)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REVOKED"


def _forge_access_token(claims: dict) -> str:
    """Sign a structurally valid access token with arbitrary claim overrides."""
    return jwt.encode(claims, settings.JWT_SIGNING_KEY, algorithm="HS256")


@pytest.mark.django_db
def test_access_tokens_without_usable_session_id_are_rejected(
    client: Client,
    administrator,
) -> None:
    base_claims = _decoded(access_token(login(client, "administrator", "Correct-Horse-42!")))

    missing_sid = me(client, _forge_access_token({**base_claims, "sid": None}))
    garbage_sid = me(client, _forge_access_token({**base_claims, "sid": "not-a-uuid"}))
    unknown_user = me(client, _forge_access_token({**base_claims, "user_id": 999_999}))

    for response in (missing_sid, garbage_sid, unknown_user):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "TOKEN_INVALID"


@pytest.mark.django_db
def test_refresh_rotates_tokens(
    client: Client,
    administrator,
) -> None:
    login_response = login(client, "administrator", "Correct-Horse-42!")
    old_access = access_token(login_response)
    old_refresh = refresh_token(login_response)

    # Refresh should succeed and return a new access token plus a new cookie.
    refresh_response = refresh(client, old_refresh)
    assert refresh_response.status_code == 200
    new_body = refresh_response.json()
    assert new_body["access"] != old_access
    assert "refresh" not in new_body
    new_refresh = refresh_token(refresh_response)
    assert new_refresh != old_refresh
    assert new_body["token_type"] == "Bearer"
    assert new_body["expires_in"] == settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS
    assert new_body["refresh_expires_in"] <= settings.JWT_REFRESH_TOKEN_LIFETIME_SECONDS
    assert new_body["user"]["username"] == "administrator"

    # Old refresh token should be rejected (session's refresh_jti has been rotated)
    reuse_response = refresh(client, old_refresh)
    assert reuse_response.status_code == 401
    assert reuse_response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    # The new refresh token is rejected too: reuse detection revoked the family.
    second_refresh = refresh(client, new_refresh)
    assert second_refresh.status_code == 401
    assert second_refresh.json()["error"]["code"] == "SESSION_REVOKED"


@pytest.mark.django_db
def test_refresh_reuse_revokes_family(client: Client, administrator) -> None:
    login_response = login(client, "administrator", "Correct-Horse-42!")
    refresh_1 = refresh_token(login_response)

    # First use of refresh token works
    first_refresh = refresh(client, refresh_1)
    assert first_refresh.status_code == 200
    refresh_2 = refresh_token(first_refresh)

    # Second use of the SAME (now consumed) refresh token should fail
    reuse_response = refresh(client, refresh_1)
    assert reuse_response.status_code == 401
    assert reuse_response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    # The session should be revoked (reuse detection revokes the family)
    session = AuthSession.objects.get(user=administrator)
    assert session.revoked_at is not None
    assert session.revoke_reason == "refresh_reuse"

    # Even the new refresh token from the first rotation should now fail
    # because the family was revoked
    after_reuse = refresh(client, refresh_2)
    assert after_reuse.status_code == 401
    assert after_reuse.json()["error"]["code"] == "SESSION_REVOKED"


@pytest.mark.django_db
def test_refresh_with_expired_session_fails(client: Client, administrator) -> None:
    login_response = login(client, "administrator", "Correct-Horse-42!")
    refresh_tok = refresh_token(login_response)
    session = AuthSession.objects.get(user=administrator)
    session.expires_at = timezone.now() - timedelta(seconds=1)
    session.save(update_fields=["expires_at"])

    response = refresh(client, refresh_tok)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REVOKED"


@pytest.mark.django_db
def test_refresh_with_malformed_token_fails(client: Client) -> None:
    response = refresh(client, "not-a-valid-token")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_refresh_without_token_fails(client: Client) -> None:
    response = post_json(client, "/api/v1/auth/refresh/", {})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_refresh_cookie_can_be_used_with_csrf(client: Client, administrator) -> None:
    login_response = login(client, "administrator", "Correct-Horse-42!")
    assert "refresh_token" in login_response.cookies
    token = csrf_token(client)

    response = client.post(
        "/api/v1/auth/refresh/",
        content_type="application/json",
        data="{}",
        HTTP_X_CSRFTOKEN=token,
    )

    assert response.status_code == 200
    assert "access" in response.json()
    assert "refresh" not in response.json()
    assert "refresh_token" in response.cookies


@pytest.mark.django_db
def test_cookie_refresh_without_csrf_is_rejected(client: Client, administrator) -> None:
    assert login(client, "administrator", "Correct-Horse-42!").status_code == 200

    blocked = client.post(
        "/api/v1/auth/refresh/",
        content_type="application/json",
        data="{}",
    )

    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "CSRF_FAILED"

    # Nothing was consumed: the same cookie still rotates with a valid token.
    token = csrf_token(client)
    retry = client.post(
        "/api/v1/auth/refresh/",
        content_type="application/json",
        data="{}",
        HTTP_X_CSRFTOKEN=token,
    )
    assert retry.status_code == 200


@pytest.mark.django_db
def test_body_refresh_does_not_require_csrf(client: Client, administrator) -> None:
    body_token = refresh_token(login(client, "administrator", "Correct-Horse-42!"))

    response = refresh(client, body_token)

    assert response.status_code == 200


@pytest.mark.django_db
def test_refresh_rejects_inactive_user(client: Client, roles) -> None:
    user = make_user("inactive-refresh")
    login_response = login(client, "inactive-refresh", "Correct-Horse-42!")
    refresh_tok = refresh_token(login_response)

    user.is_active = False
    user.save(update_fields=["is_active"])

    response = refresh(client, refresh_tok)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REVOKED"
    assert AuthSession.objects.get(user=user).revoke_reason == "account_deactivated"


@pytest.mark.django_db
def test_logout_revokes_every_session_for_the_caller(
    client: Client,
    administrator,
) -> None:
    first = login(client, "administrator", "Correct-Horse-42!")
    second = login(client, "administrator", "Correct-Horse-42!")
    first_access = access_token(first)
    second_access = access_token(second)
    first_refresh = refresh_token(first)
    second_refresh = refresh_token(second)

    response = logout(client, first_access)

    assert response.status_code == 200
    assert response.json() == {
        "message": (
            "Logout successful. All active sessions for the current user have been revoked."
        )
    }
    assert response["Cache-Control"] == "no-store"
    for token in (first_access, second_access):
        after = me(client, token)
        assert after.status_code == 401
        assert after.json()["error"]["code"] == "SESSION_REVOKED"
    # Refresh tokens stop working immediately as well.
    for token in (first_refresh, second_refresh):
        after = refresh(client, token)
        assert after.status_code == 401
        assert after.json()["error"]["code"] == "SESSION_REVOKED"
    assert AuthSession.objects.filter(user=administrator, revoked_at__isnull=True).count() == 0
    assert set(
        AuthSession.objects.filter(user=administrator).values_list("revoke_reason", flat=True)
    ) == {"logout_all"}


@pytest.mark.django_db
def test_logout_does_not_revoke_another_users_sessions(
    client: Client,
    roles,
) -> None:
    make_user("logout-a")
    make_user("logout-b")
    first = login(client, "logout-a", "Correct-Horse-42!")
    second = login(client, "logout-b", "Correct-Horse-42!")

    response = logout(client, access_token(first))

    assert response.status_code == 200
    assert me(client, access_token(first)).status_code == 401
    assert me(client, access_token(second)).status_code == 200
    assert AuthSession.objects.filter(user__username="logout-b", revoked_at__isnull=True).exists()


@pytest.mark.django_db
def test_logout_requires_an_access_token(client: Client) -> None:
    response = client.post("/api/v1/auth/logout/")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_logout_accepts_no_refresh_body(client: Client, administrator) -> None:
    access = access_token(login(client, "administrator", "Correct-Horse-42!"))

    response = client.post(
        "/api/v1/auth/logout/",
        data="{}",
        content_type="application/json",
        **auth_header(access),
    )

    assert response.status_code == 200
    assert AuthSession.objects.filter(user=administrator, revoked_at__isnull=True).count() == 0


@pytest.mark.django_db
def test_logout_clears_refresh_cookie(client: Client, administrator) -> None:
    login_response = login(client, "administrator", "Correct-Horse-42!")
    assert "refresh_token" in login_response.cookies

    access = access_token(login_response)
    logout_response = logout(client, access)
    assert logout_response.status_code == 200

    # Cookie should be cleared with the path and SameSite used to set it.
    cookie = logout_response.cookies.get("refresh_token")
    assert cookie is not None
    assert cookie["max-age"] == 0
    assert cookie["path"] == "/api/v1/auth/"
    assert cookie["samesite"] == ("Lax" if settings.DEBUG else "Strict")


@pytest.mark.django_db
def test_inactive_user_existing_session_is_rejected(client: Client, roles) -> None:
    user = make_user("deactivate-me")
    access = access_token(login(client, "deactivate-me", "Correct-Horse-42!"))

    user.is_active = False
    user.save(update_fields=["is_active"])

    response = me(client, access)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REVOKED"
    assert AuthSession.objects.get(user=user).revoke_reason == "account_deactivated"


@pytest.mark.django_db
def test_password_change_revokes_existing_sessions(client: Client, roles) -> None:
    user = make_user("password-change")
    access = access_token(login(client, "password-change", "Correct-Horse-42!"))

    user.set_password("Another-Strong-Password-42!")
    user.save(update_fields=["password"])

    response = me(client, access)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REVOKED"
    assert AuthSession.objects.get(user=user).revoke_reason == "password_changed"
    assert login(client, "password-change", "Another-Strong-Password-42!").status_code == 200
    assert login(client, "password-change", "Correct-Horse-42!").status_code == 401


@pytest.mark.django_db
def test_me_rejects_writes(client: Client, administrator) -> None:
    access = access_token(login(client, "administrator", "Correct-Horse-42!"))

    for method in (client.put, client.patch, client.delete):
        response = method(
            "/api/v1/auth/me/",
            data='{"is_staff": true}',
            content_type="application/json",
            **auth_header(access),
        )
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


@pytest.mark.django_db
def test_no_public_registration_endpoint(client: Client) -> None:
    response = post_json(
        client,
        "/api/v1/auth/register/",
        {"username": "new", "password": "something-long"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_access_token_class_uses_configured_lifetime() -> None:
    token = AccessToken()
    assert settings.SIMPLE_JWT["ALGORITHM"] == "HS256"
    assert settings.SIMPLE_JWT["AUTH_HEADER_TYPES"] == ("Bearer",)
    assert settings.SIMPLE_JWT["SIGNING_KEY"] != settings.SECRET_KEY
    assert settings.SIMPLE_JWT["AUTH_TOKEN_CLASSES"] == (
        "rest_framework_simplejwt.tokens.AccessToken",
    )
    assert token.lifetime == timedelta(seconds=settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS)
    assert settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] == timedelta(
        seconds=settings.JWT_REFRESH_TOKEN_LIFETIME_SECONDS
    )
    assert settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"] is True
    assert settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"] is True


@pytest.mark.django_db
def test_access_and_refresh_tokens_with_wrong_algorithm_are_rejected(
    client: Client,
    administrator,
) -> None:
    login_response = login(client, "administrator", "Correct-Horse-42!")
    access_claims = _decoded(access_token(login_response))
    refresh_value = refresh_token(login_response)
    refresh_claims = jwt.decode(
        refresh_value,
        settings.JWT_SIGNING_KEY,
        algorithms=["HS256"],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
    )

    def encode_with(claims: dict, algorithm: str) -> str:
        return jwt.encode(
            claims,
            settings.JWT_SIGNING_KEY if algorithm != "none" else "",
            algorithm=algorithm,
        )

    for algorithm in ("HS512", "none"):
        access_response = me(client, encode_with(access_claims, algorithm))
        assert access_response.status_code == 401
        assert access_response.json()["error"]["code"] == "TOKEN_INVALID"

        refresh_response = refresh(client, encode_with(refresh_claims, algorithm))
        assert refresh_response.status_code == 401
        assert refresh_response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_cookie_refresh_with_invalid_csrf_token_is_rejected(
    client: Client,
    administrator,
) -> None:
    assert login(client, "administrator", "Correct-Horse-42!").status_code == 200

    blocked = client.post(
        "/api/v1/auth/refresh/",
        content_type="application/json",
        data="{}",
        HTTP_X_CSRFTOKEN="not-the-csrf-token",
    )

    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "CSRF_FAILED"


@pytest.mark.django_db
def test_refresh_fails_closed_when_rotation_raises(
    client: Client,
    administrator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = refresh_token(login(client, "administrator", "Correct-Horse-42!"))

    def explode(*args: object, **kwargs: object) -> object:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("accounts.views.rotate_refresh_token", explode)

    response = refresh(client, token)

    # A database/rotation failure is denied, never reported as success.
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"
    assert "access" not in response.json()
    assert "refresh_token" not in response.cookies
    body = response.content.decode()
    assert "database unavailable" not in body
    assert "Traceback" not in body


@pytest.mark.django_db
def test_refresh_works_after_the_access_token_expired(
    client: Client,
    administrator,
) -> None:
    login_response = login(client, "administrator", "Correct-Horse-42!")
    claims = _decoded(access_token(login_response))
    now = datetime.now(tz=UTC)
    expired_access = jwt.encode(
        {
            **claims,
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
        },
        settings.JWT_SIGNING_KEY,
        algorithm="HS256",
    )
    assert me(client, expired_access).status_code == 401

    refreshed = refresh(client, refresh_token(login_response))

    assert refreshed.status_code == 200
    assert me(client, refreshed.json()["access"]).status_code == 200


@pytest.mark.django_db
def test_refresh_rejects_wrong_issuer_audience_and_token_type(
    client: Client,
    administrator,
) -> None:
    login_response = login(client, "administrator", "Correct-Horse-42!")
    refresh_value = refresh_token(login_response)
    claims = jwt.decode(
        refresh_value,
        settings.JWT_SIGNING_KEY,
        algorithms=["HS256"],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
    )

    wrong_issuer = jwt.encode(
        {**claims, "iss": "another-service"},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256",
    )
    wrong_audience = jwt.encode(
        {**claims, "aud": "another-service"},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256",
    )
    access_as_refresh = access_token(login_response)

    for candidate in (wrong_issuer, wrong_audience, access_as_refresh):
        response = refresh(client, candidate)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_expired_refresh_token_is_rejected(client: Client, administrator) -> None:
    login(client, "administrator", "Correct-Horse-42!")
    session = AuthSession.objects.get(user=administrator)
    expired = RefreshToken.for_user(administrator)
    expired["jti"] = session.refresh_jti
    expired["fam"] = str(session.family_id)
    expired.set_exp(
        from_time=timezone.now() - timedelta(days=2),
        lifetime=timedelta(seconds=1),
    )

    response = refresh(client, str(expired))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_access_token_with_wrong_issuer_or_audience_is_rejected(
    client: Client,
    administrator,
) -> None:
    claims = _decoded(access_token(login(client, "administrator", "Correct-Horse-42!")))
    wrong_issuer = jwt.encode(
        {**claims, "iss": "another-service"},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256",
    )
    wrong_audience = jwt.encode(
        {**claims, "aud": "another-service"},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256",
    )

    for candidate in (wrong_issuer, wrong_audience):
        response = me(client, candidate)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "TOKEN_INVALID"


@pytest.mark.django_db
def test_rotation_does_not_extend_the_absolute_session_expiry(
    client: Client,
    administrator,
) -> None:
    login_response = login(client, "administrator", "Correct-Horse-42!")
    session = AuthSession.objects.get(user=administrator)
    original_expiry = session.expires_at

    rotated = refresh(client, refresh_token(login_response))

    assert rotated.status_code == 200
    session.refresh_from_db()
    assert session.expires_at == original_expiry
    new_refresh_claims = jwt.decode(
        refresh_token(rotated),
        settings.JWT_SIGNING_KEY,
        algorithms=["HS256"],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
    )
    assert new_refresh_claims["exp"] <= int(original_expiry.timestamp())


@pytest.mark.django_db
def test_logout_then_fresh_login_succeeds(administrator) -> None:
    first_client = Client()
    access = access_token(login(first_client, "administrator", "Correct-Horse-42!"))
    assert logout(first_client, access).status_code == 200

    second_client = Client()
    second_login = login(second_client, "administrator", "Correct-Horse-42!")

    assert second_login.status_code == 200
    assert me(second_client, access_token(second_login)).status_code == 200


@pytest.mark.django_db
def test_cookie_refresh_after_logout_is_rejected(client: Client, administrator) -> None:
    assert login(client, "administrator", "Correct-Horse-42!").status_code == 200
    access = access_token(login(client, "administrator", "Correct-Horse-42!"))

    assert logout(client, access).status_code == 200

    response = client.post(
        "/api/v1/auth/refresh/",
        content_type="application/json",
        data="{}",
    )

    assert response.status_code == 401
    assert "access" not in response.json()


@pytest.mark.django_db
def test_logout_fails_closed_when_revocation_fails(
    client: Client,
    administrator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    access = access_token(login(client, "administrator", "Correct-Horse-42!"))

    def explode(*args: object, **kwargs: object) -> int:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("accounts.views.revoke_user_sessions", explode)

    response = logout(client, access)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    body = response.content.decode()
    assert "Logout successful" not in body
    assert "database unavailable" not in body
    # The session survives because revocation did not commit.
    assert AuthSession.objects.filter(user=administrator, revoked_at__isnull=True).count() == 1


@pytest.mark.django_db
def test_login_fails_closed_when_session_creation_fails(
    client: Client,
    administrator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*args: object, **kwargs: object) -> object:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("accounts.views.create_auth_session", explode)

    response = login(client, "administrator", "Correct-Horse-42!")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "access" not in response.json()
    assert "refresh_token" not in response.cookies
    assert "database unavailable" not in response.content.decode()
