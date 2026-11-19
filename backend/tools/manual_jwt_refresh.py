"""Manual live-server check: refresh rotation, reuse rejection and CSRF handling.

Run from ``backend/`` with::

    python -m tools.manual_jwt_refresh

Credentials are read from ``MYTROLLEY_USERNAME`` / ``MYTROLLEY_PASSWORD`` or
prompted for at runtime.
"""

from __future__ import annotations

import requests

from tools._manual_auth import auth_base_url, check_me, credentials, login


def main() -> None:
    """Exercise login, cookie refresh, token rotation and old-token rejection."""
    username, password = credentials()
    session = requests.Session()
    access, csrf, old_refresh = login(session, username, password)
    check_me(access, 200, "initial access token works")

    refresh = session.post(
        auth_base_url() + "refresh/",
        json={},
        headers={"X-CSRFToken": csrf},
        timeout=15,
    )
    if refresh.status_code != 200:
        raise RuntimeError(f"Refresh failed with HTTP {refresh.status_code}.")
    refresh_data = refresh.json()
    new_access = refresh_data.get("access")
    new_refresh = session.cookies.get("refresh_token")
    if not isinstance(new_access, str) or not new_refresh or new_refresh == old_refresh:
        raise RuntimeError("Refresh did not return a new access token and rotated cookie.")
    check_me(new_access, 200, "rotated access token works")

    replay = requests.post(
        auth_base_url() + "refresh/",
        json={"refresh": old_refresh},
        timeout=15,
    )
    if replay.status_code not in (400, 401, 403):
        raise RuntimeError(f"Old refresh token was not rejected (HTTP {replay.status_code}).")
    print("PASS: refresh rotated the cookie and the old token was rejected")


if __name__ == "__main__":
    main()
