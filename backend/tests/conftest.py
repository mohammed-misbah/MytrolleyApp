"""Shared test fixtures and CSRF-aware request helpers."""

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
    """A client that really enforces CSRF checks."""
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


def fetch_csrf(client: Client) -> str:
    """Bootstrap a CSRF cookie/token through the public endpoint."""
    response = client.get("/api/v1/auth/csrf/")
    assert response.status_code == 200
    return response.json()["csrfToken"]


def post_json(
    client: Client,
    url: str,
    payload: dict[str, Any] | str,
    *,
    csrf_token: str | None = None,
    content_type: str = "application/json",
    **extra: Any,
):
    """POST JSON with an explicit CSRF header when one is supplied."""
    body = payload if isinstance(payload, str) else json.dumps(payload)
    headers = dict(extra)
    if csrf_token is not None:
        headers["HTTP_X_CSRFTOKEN"] = csrf_token
    return client.post(url, data=body, content_type=content_type, **headers)


def login(
    client: Client,
    username: str,
    password: str,
    *,
    csrf_token: str | None = None,
):
    """Log in using a freshly bootstrapped CSRF token by default."""
    token = csrf_token if csrf_token is not None else fetch_csrf(client)
    return post_json(
        client,
        "/api/v1/auth/login/",
        {"username": username, "password": password},
        csrf_token=token,
    )


def logout(client: Client):
    """Log out using a fresh CSRF token (login rotates it)."""
    return post_json(
        client,
        "/api/v1/auth/logout/",
        {},
        csrf_token=fetch_csrf(client),
    )
