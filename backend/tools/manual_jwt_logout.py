"""Manual live-server check: logout revokes all sessions of one account.

Run from ``backend/`` with::

    python -m tools.manual_jwt_logout

Credentials are read from ``MYTROLLEY_USERNAME`` / ``MYTROLLEY_PASSWORD`` or
prompted for at runtime.
"""

from __future__ import annotations

import requests

from tools._manual_auth import check_me, credentials, login, logout


def main() -> None:
    """Exercise login, logout and post-logout token rejection."""
    username, password = credentials()
    session = requests.Session()
    access, csrf, _refresh = login(session, username, password)
    check_me(access, 200, "access token works before logout")
    logout(session, access, csrf)
    check_me(access, 401, "access token rejected after logout")
    print("PASS: logout revoked the session")


if __name__ == "__main__":
    main()
