"""Shared helpers for the manual JWT live-server checks.

These helpers are for interactive verification only. Credentials come from
environment variables (``MYTROLLEY_USERNAME`` / ``MYTROLLEY_PASSWORD``, with
an optional ``_A`` / ``_B`` suffix) and fall back to a prompt at runtime.
Nothing here reads credentials at import time.
"""

from __future__ import annotations

import os
from getpass import getpass

import requests

DEFAULT_AUTH_BASE_URL = "http://127.0.0.1:8000/api/v1/auth/"


def auth_base_url() -> str:
    """Return the authentication endpoint prefix with a trailing slash."""
    configured = os.environ.get("MYTROLLEY_AUTH_BASE_URL", DEFAULT_AUTH_BASE_URL)
    return configured.rstrip("/") + "/"


def credentials(label: str = "") -> tuple[str, str]:
    """Read one account from the environment, prompting only when run live."""
    suffix = f"_{label}" if label else ""
    username = os.environ.get(f"MYTROLLEY_USERNAME{suffix}")
    password = os.environ.get(f"MYTROLLEY_PASSWORD{suffix}")
    if not username:
        username = input(f"Username{(' ' + label) if label else ''}: ")
    if not password:
        password = getpass("Password: ")
    return username, password


def login(session: requests.Session, username: str, password: str) -> tuple[str, str, str]:
    """Log in and return (access token, CSRF cookie, refresh cookie)."""
    response = session.post(
        auth_base_url() + "login/",
        json={"username": username, "password": password},
        timeout=15,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Login failed with HTTP {response.status_code}.")
    payload = response.json()
    access = payload.get("access")
    csrf = session.cookies.get("csrftoken")
    refresh = session.cookies.get("refresh_token")
    if not isinstance(access, str) or not csrf or not refresh:
        raise RuntimeError("Login response did not contain the expected token material.")
    return access, csrf, refresh


def logout(session: requests.Session, access: str, csrf: str) -> None:
    """Revoke every session for the authenticated account."""
    response = session.post(
        auth_base_url() + "logout/",
        headers={"Authorization": f"Bearer {access}", "X-CSRFToken": csrf},
        timeout=15,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Logout failed with HTTP {response.status_code}.")


def check_me(access: str, expected_status: int, label: str) -> None:
    """Assert the /me/ endpoint returns the expected status for a token."""
    response = requests.get(
        auth_base_url() + "me/",
        headers={"Authorization": f"Bearer {access}"},
        timeout=15,
    )
    if response.status_code != expected_status:
        raise RuntimeError(f"{label}: expected HTTP {expected_status}, got {response.status_code}.")
    print(f"PASS: {label}")
