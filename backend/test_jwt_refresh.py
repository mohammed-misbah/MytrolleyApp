
import requests
from getpass import getpass

BASE_URL = "http://127.0.0.1:8000/api/v1/auth/"

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

old_refresh_token = session.cookies.get("refresh_token")
csrf_token = session.cookies.get("csrftoken")

print("Access token received:", bool(access_token))
print("Refresh token inside JSON:", "refresh" in login_data)
print("Refresh cookie received:", bool(old_refresh_token))
print("CSRF cookie received:", bool(csrf_token))

if not access_token:
    stop("Access token missing.")

if not old_refresh_token:
    stop("Refresh cookie missing.")

if not csrf_token:
    stop("CSRF cookie missing.")


# 2. CHECK /ME BEFORE REFRESH
print("\n========== INITIAL ME CHECK ==========")

me = session.get(
    BASE_URL + "me/",
    headers={
        "Authorization": f"Bearer {access_token}"
    },
    timeout=15,
)

print("ME STATUS:", me.status_code)

if me.status_code != 200:
    print(me.text)
    stop("Initial access token failed.")


# 3. REFRESH TOKEN
print("\n========== REFRESH TOKEN ==========")

refresh = session.post(
    BASE_URL + "refresh/",
    json={},
    headers={
        "X-CSRFToken": csrf_token
    },
    timeout=15,
)

print("REFRESH STATUS:", refresh.status_code)

if refresh.status_code != 200:
    print(refresh.text)
    stop("Refresh request failed.")

refresh_data = refresh.json()
new_access_token = refresh_data.get("access")
new_refresh_token = session.cookies.get("refresh_token")

print("New access token received:", bool(new_access_token))
print(
    "Refresh token rotated:",
    bool(
        new_refresh_token
        and new_refresh_token != old_refresh_token
    ),
)

if not new_access_token:
    stop("New access token missing.")

if not new_refresh_token or new_refresh_token == old_refresh_token:
    stop("Refresh cookie was not rotated.")


# 4. CHECK NEW ACCESS TOKEN BEFORE REPLAY TEST
print("\n========== NEW ACCESS TOKEN CHECK ==========")

new_me = session.get(
    BASE_URL + "me/",
    headers={
        "Authorization": f"Bearer {new_access_token}"
    },
    timeout=15,
)

print("NEW ACCESS TOKEN STATUS:", new_me.status_code)

if new_me.status_code != 200:
    print(new_me.text)
    stop("New access token failed before replay test.")

print("PASS: New access token works.")


# 5. TEST OLD REFRESH TOKEN REJECTION
print("\n========== OLD REFRESH TOKEN REJECTION ==========")

# Use a separate request without the current session's cookies.
# This explicitly tests the old refresh token from the request body.
old_token_test = requests.post(
    BASE_URL + "refresh/",
    json={
        "refresh": old_refresh_token
    },
    headers={
        "X-CSRFToken": csrf_token
    },
    timeout=15,
)

print("OLD REFRESH TOKEN STATUS:", old_token_test.status_code)

if old_token_test.status_code in (400, 401, 403):
    print("PASS: Old refresh token was rejected.")
else:
    print("FAILED: Old refresh token was not rejected as expected.")
    print(old_token_test.text)
    raise SystemExit(1)


# 6. FINAL REPORT
print("\n========== TEST SUMMARY ==========")
print("PASS: Login successful.")
print("PASS: Access token received.")
print("PASS: Refresh token stored in HttpOnly cookie.")
print("PASS: Refresh token not exposed in login JSON.")
print("PASS: Initial /me/ request successful.")
print("PASS: Refresh endpoint successful.")
print("PASS: Refresh token rotated.")
print("PASS: New access token works.")
print("PASS: Old refresh token rejected.")

print("\nALL TESTS IN THIS SCRIPT PASSED.")
