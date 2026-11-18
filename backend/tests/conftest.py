"""Shared test fixtures and JWT-aware request helpers."""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client

from accounts.roles import ROLE_ADMINISTRATOR, ROLE_DATA_ENTRY, seed_roles

User = get_user_model()


@pytest.fixture
def client() -> Client:
    """A client that really enforces CSRF checks.

    JWT Bearer endpoints must still work because the API is not cookie
    authenticated. This fixture proves that CSRF is not silently required.
    """
    return Client(enforce_csrf_checks=True)


@pytest.fixture
def roles(db) -> dict[str, Group]:
    """Ensure the declarative roles exist in the test database."""
    return seed_roles()


def make_user(
    username: str,
    password: str = "Correct-Horse-42!",
    *,
    role: str | None = None,
    is_active: bool = True,
    is_staff: bool = False,
) -> Any:
    """Create a test user, optionally in one assessment role."""
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password=password,
        is_active=is_active,
        is_staff=is_staff,
    )
    if role is not None:
        user.groups.add(Group.objects.get(name=role))
    return user


@pytest.fixture
def administrator(roles):
    return make_user("administrator", role=ROLE_ADMINISTRATOR, is_staff=True)


@pytest.fixture
def data_entry(roles):
    return make_user("dataentry", role=ROLE_DATA_ENTRY)


def post_json(
    client: Client,
    url: str,
    payload: dict[str, Any] | str,
    **extra: Any,
):
    """POST JSON without any CSRF header."""
    body = payload if isinstance(payload, str) else json.dumps(payload)
    return client.post(
        url,
        data=body,
        content_type="application/json",
        **extra,
    )


def auth_header(access_token: str) -> dict[str, str]:
    """Build the DRF/Django test-client Authorization header."""
    return {"HTTP_AUTHORIZATION": f"Bearer {access_token}"}


def login(
    client: Client,
    username: str,
    password: str,
    **extra: Any,
):
    """Log in through the JWT endpoint and return the raw response."""
    return post_json(
        client,
        "/api/v1/auth/login/",
        {"username": username, "password": password},
        **extra,
    )


def access_token(response: Any) -> str:
    return str(response.json()["access"])


def refresh_token(response: Any) -> str:
    """Read the refresh token from the HttpOnly cookie set by the API.

    The JSON body never contains it, by design.
    """
    return str(response.cookies["refresh_token"].value)


def csrf_token(client: Client) -> str:
    """Return the CSRF cookie issued by login.

    Login sets a readable ``csrftoken`` cookie alongside the HttpOnly refresh
    cookie. A browser echoes that value in ``X-CSRFToken`` when it refreshes
    from the cookie; there is no separate bootstrap endpoint.
    """
    return str(client.cookies["csrftoken"].value)


def me(client: Client, token: str):
    return client.get("/api/v1/auth/me/", **auth_header(token))


def refresh(client: Client, token: str, **extra: Any):
    return post_json(
        client,
        "/api/v1/auth/refresh/",
        {"refresh": token},
        **extra,
    )


def logout(client: Client, access: str):
    """POST the logout endpoint with only the access token."""
    return client.post("/api/v1/auth/logout/", **auth_header(access))
