
import requests
from getpass import getpass

BASE_URL = "http://127.0.0.1:8000/api/v1/auth/"

EXPECTED_LOGOUT_MESSAGE = (
    "Logout successful. All active sessions for the current user "
    "have been revoked."
)

username = input("Enter username: ")
password = getpass("Enter password: ")

session = requests.Session()


def stop(message):
    print("\nFAILED:", message)
    raise SystemExit(1)


# 1. LOGIN
print("\n========== LOGIN ==========")

login = session.post(
    BASE_URL + "login/",
    json={
        "username": username,
        "password": password,
    },
    timeout=15,
)

print("LOGIN STATUS:", login.status_code)

if login.status_code != 200:
    print(login.text)
    stop("Login failed.")

login_data = login.json()
access_token = login_data.get("access")
refresh_token = session.cookies.get("refresh_token")
csrf_token = session.cookies.get("csrftoken")

print("Access token received:", bool(access_token))
print("Refresh cookie received:", bool(refresh_token))

if not access_token or not refresh_token:
    stop("Access or refresh token missing.")

if not csrf_token:
    stop("CSRF cookie missing.")


# 2. CHECK ACCESS TOKEN BEFORE LOGOUT
print("\n========== BEFORE LOGOUT ==========")

me_before = session.get(
    BASE_URL + "me/",
    headers={
        "Authorization": f"Bearer {access_token}"
    },
    timeout=15,
)

print("ME BEFORE LOGOUT:", me_before.status_code)

if me_before.status_code != 200:
    stop("Access token was not working before logout.")


# 3. LOGOUT
print("\n========== LOGOUT ==========")

logout = session.post(
    BASE_URL + "logout/",
    headers={
        "Authorization": f"Bearer {access_token}",
        "X-CSRFToken": csrf_token,
    },
    timeout=15,
)

print("LOGOUT STATUS:", logout.status_code)

try:
    logout_data = logout.json()
except ValueError:
    logout_data = {}

print("LOGOUT RESPONSE:", logout_data)

if logout.status_code != 200:
    stop("Logout did not return HTTP 200.")

if logout_data.get("message") != EXPECTED_LOGOUT_MESSAGE:
    stop("Logout response message does not match the expected message.")

print("PASS: Logout returned the expected success message.")


# 4. CHECK OLD ACCESS TOKEN
print("\n========== OLD ACCESS TOKEN CHECK ==========")

old_me = session.get(
    BASE_URL + "me/",
    headers={
        "Authorization": f"Bearer {access_token}"
    },
    timeout=15,
)

print("OLD ACCESS TOKEN STATUS:", old_me.status_code)

if old_me.status_code == 401:
    print("PASS: Old access token was revoked.")
else:
    print("Response:", old_me.text)
    stop("Old access token was not rejected.")


# 5. CHECK OLD REFRESH TOKEN
print("\n========== OLD REFRESH TOKEN CHECK ==========")

old_refresh_test = requests.post(
    BASE_URL + "refresh/",
    json={
        "refresh": refresh_token
    },
    headers={
        "X-CSRFToken": csrf_token
    },
    timeout=15,
)

print("OLD REFRESH TOKEN STATUS:", old_refresh_test.status_code)

if old_refresh_test.status_code in (400, 401, 403):
    print("PASS: Old refresh token was revoked.")
else:
    print("Response:", old_refresh_test.text)
    stop("Old refresh token was not rejected.")


# 6. CHECK REFRESH COOKIE CLEARING
print("\n========== REFRESH COOKIE CHECK ==========")

remaining_cookie = session.cookies.get("refresh_token")

print("Refresh cookie remaining:", bool(remaining_cookie))

if remaining_cookie:
    stop("Refresh cookie was not cleared from the client session.")

print("PASS: Refresh cookie cleared.")


# 7. FRESH LOGIN AFTER LOGOUT
print("\n========== FRESH LOGIN CHECK ==========")

fresh_session = requests.Session()

fresh_login = fresh_session.post(
    BASE_URL + "login/",
    json={
        "username": username,
        "password": password,
    },
    timeout=15,
)

print("FRESH LOGIN STATUS:", fresh_login.status_code)

if fresh_login.status_code == 200:
    print("PASS: Fresh login works after logout.")
else:
    print(fresh_login.text)
    stop("Fresh login failed after logout.")


# 8. FINAL SUMMARY
print("\n========== FINAL TEST SUMMARY ==========")

print("PASS: Login successful.")
print("PASS: Access token worked before logout.")
print("PASS: Logout returned HTTP 200.")
print("PASS: Exact logout success message received.")
print("PASS: Old access token rejected.")
print("PASS: Old refresh token rejected.")
print("PASS: Refresh cookie cleared.")
print("PASS: Fresh login successful.")

print("\nALL LOGOUT TESTS PASSED.")
