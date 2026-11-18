"""Regression test for the read-only account information returned by /me/."""

from __future__ import annotations

import pytest
from django.test import Client

from tests.conftest import access_token, auth_header, login


@pytest.mark.django_db
def test_me_returns_extended_safe_profile(client: Client, administrator) -> None:
    token = access_token(login(client, "administrator", "Correct-Horse-42!"))
    response = client.get("/api/v1/auth/me/", **auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "administrator"
    assert body["full_name"] == administrator.get_full_name().strip()
    assert body["email"] == administrator.email
    assert body["roles"] == ["Administrator"]
    assert body["is_active"] is True
    assert body["date_joined"]
    assert body["updated_at"]
    assert "password" not in body
    assert "refresh" not in body


@pytest.mark.django_db
def test_removed_profile_management_endpoints_are_gone(client: Client, administrator) -> None:
    token = access_token(login(client, "administrator", "Correct-Horse-42!"))
    headers = auth_header(token)

    assert client.patch("/api/v1/auth/profile/", {"first_name": "X"}, **headers).status_code == 404
    assert client.post("/api/v1/auth/change-password/", {}, **headers).status_code == 404
