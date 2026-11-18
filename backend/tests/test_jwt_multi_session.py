
import requests
from getpass import getpass

BASE_URL = "http://127.0.0.1:8000/api/v1/auth/"


def login(username, password):
    session = requests.Session()

    response = session.post(
        BASE_URL + "login/",
        json={
            "username": username,
            "password": password,
        },
        timeout=15,
    )

    print(f"\nLOGIN {username}: {response.status_code}")

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(f"Login failed for {username}")

    access = response.json().get("access")
    csrf = session.cookies.get("csrftoken")

    if not access or not csrf:
        raise SystemExit("Access token or CSRF cookie missing.")

    return session, access, csrf


def check_me(access, expected_status, label):
    response = requests.get(
        BASE_URL + "me/",
        headers={"Authorization": f"Bearer {access}"},
        timeout=15,
    )

    print(f"{label}: {response.status_code}")

    if response.status_code != expected_status:
        print(response.text)
        raise SystemExit(f"FAILED: {label}")

    print(f"PASS: {label}")


print("========== ENTER TEST ACCOUNTS ==========")

user_a = input("User A username (Misbah): ")
password_a = getpass("User A password: ")

user_b = input("User B username: ")
password_b = getpass("User B password: ")


# 1. LOGIN USER A TWICE
print("\n========== USER A: TWO LOGINS ==========")

session_a1, access_a1, csrf_a1 = login(user_a, password_a)
session_a2, access_a2, csrf_a2 = login(user_a, password_a)

# 2. LOGIN USER B
print("\n========== USER B: LOGIN ==========")

session_b, access_b, csrf_b = login(user_b, password_b)

# 3. VERIFY ALL THREE SESSIONS WORK
print("\n========== BEFORE LOGOUT ==========")

check_me(access_a1, 200, "User A session 1")
check_me(access_a2, 200, "User A session 2")
check_me(access_b, 200, "User B session")

# 4. LOGOUT USER A
print("\n========== LOGOUT USER A ==========")

logout = session_a2.post(
    BASE_URL + "logout/",
    headers={
        "Authorization": f"Bearer {access_a2}",
        "X-CSRFToken": csrf_a2,
    },
    timeout=15,
)

print("LOGOUT STATUS:", logout.status_code)

if logout.status_code != 200:
    print(logout.text)
    raise SystemExit("User A logout failed.")

print("PASS: User A logout succeeded.")

# 5. CHECK BOTH USER A SESSIONS
print("\n========== USER A REVOCATION CHECK ==========")

check_me(access_a1, 401, "User A session 1 revoked")
check_me(access_a2, 401, "User A session 2 revoked")

# 6. CHECK USER B IS STILL WORKING
print("\n========== USER B PROTECTION CHECK ==========")

check_me(access_b, 200, "User B session remains valid")

print("\n========== FINAL RESULT ==========")
print("PASS: Both User A sessions were revoked.")
print("PASS: User B session remained valid.")
print("\nALL MULTI-SESSION TESTS PASSED.")
