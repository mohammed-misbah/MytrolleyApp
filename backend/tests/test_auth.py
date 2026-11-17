"""Authentication, session and CSRF behaviour."""

from __future__ import annotations

import json

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import Client

from accounts.roles import ROLE_ADMINISTRATOR
from tests.conftest import fetch_csrf, login, logout, make_user, post_json


@pytest.mark.django_db
def test_csrf_bootstrap_sets_cookie_and_token(client: Client) -> None:
    response = client.get("/api/v1/auth/csrf/")

    assert response.status_code == 200
    token = response.json()["csrfToken"]
    assert token
    cookie = client.cookies["csrftoken"]
    assert cookie.value
    # The response carries a masked token derived from the cookie secret.
    assert token != cookie.value
    assert cookie["httponly"] in (False, "")
    assert response["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_valid_login_returns_safe_user_and_rotates_session(
    client: Client,
    administrator,
) -> None:
    client.session["pre_login_probe"] = "present"
    client.session.save()
    old_session_key = client.session.session_key
    old_csrf = fetch_csrf(client)

    response = login(client, "administrator", "Correct-Horse-42!")

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "administrator"
    assert body["email"] == "administrator@example.test"
    assert body["roles"] == [ROLE_ADMINISTRATOR]
    assert body["is_staff"] is True
    assert "accounts.manage_users" in body["permissions"]
    assert "accounts.manage_catalog" in body["permissions"]
    for forbidden in ("password", "last_login", "session", "user_permissions"):
        assert forbidden not in body

    new_session_key = client.session.session_key
    assert new_session_key
    assert new_session_key != old_session_key
    assert not Session.objects.filter(session_key=old_session_key).exists()

    new_csrf = client.cookies["csrftoken"].value
    assert new_csrf and new_csrf != old_csrf
    assert response["Cache-Control"] == "no-store"
    assert response.cookies["sessionid"]["httponly"] is True
    assert response.cookies["sessionid"]["samesite"] == "Lax"


@pytest.mark.django_db
def test_login_is_available_to_already_authenticated_user(
    client: Client,
    administrator,
) -> None:
    assert login(client, "administrator", "Correct-Horse-42!").status_code == 200
    assert login(client, "administrator", "Correct-Horse-42!").status_code == 200


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


@pytest.mark.django_db
def test_login_without_csrf_is_rejected(client: Client, administrator) -> None:
    fetch_csrf(client)
    response = post_json(
        client,
        "/api/v1/auth/login/",
        {"username": "administrator", "password": "Correct-Horse-42!"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"
    assert "CSRF" in response.json()["error"]["message"]
    assert "administrator" not in response.content.decode()


@pytest.mark.django_db
def test_login_with_invalid_csrf_is_rejected(client: Client, administrator) -> None:
    fetch_csrf(client)
    response = post_json(
        client,
        "/api/v1/auth/login/",
        {"username": "administrator", "password": "Correct-Horse-42!"},
        csrf_token="invalid-token",
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


@pytest.mark.django_db
def test_login_with_origin_mismatch_is_rejected(client: Client, administrator) -> None:
    token = fetch_csrf(client)
    response = post_json(
        client,
        "/api/v1/auth/login/",
        {"username": "administrator", "password": "Correct-Horse-42!"},
        csrf_token=token,
        HTTP_ORIGIN="https://attacker.example",
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


@pytest.mark.django_db
def test_logout_invalidates_session_and_requires_csrf(
    client: Client,
    administrator,
) -> None:
    assert login(client, "administrator", "Correct-Horse-42!").status_code == 200
    session_key = client.session.session_key
    old_csrf = client.cookies["csrftoken"].value

    missing_csrf = post_json(client, "/api/v1/auth/logout/", {})
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "CSRF_FAILED"
    assert client.get("/api/v1/auth/me/").status_code == 200

    response = logout(client)
    assert response.status_code == 204
    assert not Session.objects.filter(session_key=session_key).exists()
    assert client.get("/api/v1/auth/me/").status_code == 401
    assert client.cookies["csrftoken"].value != old_csrf


@pytest.mark.django_db
def test_anonymous_logout_is_unauthenticated_not_forbidden(client: Client) -> None:
    response = post_json(client, "/api/v1/auth/logout/", {})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_inactive_user_session_is_rejected(client: Client, roles) -> None:
    user = make_user("deactivate-me")
    assert login(client, "deactivate-me", "Correct-Horse-42!").status_code == 200

    user.is_active = False
    user.save(update_fields=["is_active"])

    response = client.get("/api/v1/auth/me/")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_me_requires_authentication_and_rejects_writes(
    client: Client,
    administrator,
) -> None:
    anonymous = client.get("/api/v1/auth/me/")
    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "UNAUTHENTICATED"

    assert login(client, "administrator", "Correct-Horse-42!").status_code == 200
    token = fetch_csrf(client)
    for method in (client.put, client.patch, client.delete):
        response = method(
            "/api/v1/auth/me/",
            data=json.dumps({"is_staff": True}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_session_configuration_documents_expiry() -> None:
    assert settings.SESSION_COOKIE_AGE == 28_800
    assert settings.SESSION_SAVE_EVERY_REQUEST is True
    assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is False
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.CSRF_COOKIE_HTTPONLY is False
    assert settings.CSRF_COOKIE_SAMESITE == "Lax"


@pytest.mark.django_db
def test_no_public_registration_endpoint(client: Client) -> None:
    response = client.post(
        "/api/v1/auth/register/",
        data=json.dumps({"username": "new", "password": "something-long"}),
        content_type="application/json",
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
