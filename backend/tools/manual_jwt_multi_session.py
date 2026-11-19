"""Manual live-server check: logout revokes two sessions without affecting another account.

Run from ``backend/`` with::

    python -m tools.manual_jwt_multi_session

Credentials are read from ``MYTROLLEY_USERNAME_A`` / ``MYTROLLEY_PASSWORD_A``
and ``MYTROLLEY_USERNAME_B`` / ``MYTROLLEY_PASSWORD_B``, or prompted for at runtime.
"""

from __future__ import annotations

import requests

from tools._manual_auth import check_me, credentials, login, logout


def main() -> None:
    """Exercise two logins, logout of one account and isolation of the other."""
    user_a, password_a = credentials("A")
    user_b, password_b = credentials("B")

    session_a1 = requests.Session()
    session_a2 = requests.Session()
    session_b = requests.Session()
    access_a1, csrf_a1, _ = login(session_a1, user_a, password_a)
    access_a2, csrf_a2, _ = login(session_a2, user_a, password_a)
    access_b, _csrf_b, _ = login(session_b, user_b, password_b)

    check_me(access_a1, 200, "account A session 1 works before logout")
    check_me(access_a2, 200, "account A session 2 works before logout")
    check_me(access_b, 200, "account B session works before logout")

    logout(session_a2, access_a2, csrf_a2)

    check_me(access_a1, 401, "account A session 1 revoked")
    check_me(access_a2, 401, "account A session 2 revoked")
    check_me(access_b, 200, "account B session remains valid")
    print("PASS: both account A sessions revoked; account B unaffected")


if __name__ == "__main__":
    main()
