# API Contract — Milestone 1

Base path: `/api/v1`. Request and response bodies are JSON; the parser accepts
only `application/json` and the renderer returns JSON. There is no CORS
configuration because the deployment is same-origin (the React build and Django
are served by the same reverse proxy in production). The browser never sends
cross-origin credentialed requests.

## Authentication model

The API issues **JWT access tokens** for API calls and **refresh tokens** for
automatic renewal:

| Token | Delivered as | Lifetime (default) | Used for |
|---|---|---|---|
| Access | JSON `access` field | 300 seconds | `Authorization: Bearer <access>` |
| Refresh | `HttpOnly` cookie only | 86,400 seconds, capped by the absolute session limit | Renewing the access token |

Lifetime defaults live in `backend/.env` as
`JWT_ACCESS_TOKEN_LIFETIME_SECONDS`, `JWT_REFRESH_TOKEN_LIFETIME_SECONDS` and
`JWT_ABSOLUTE_SESSION_SECONDS` (7 days). Rotation never extends a session past
its absolute expiry.

The refresh token is deliberately **not** in the login JSON. Page script cannot
read it, so XSS cannot copy it into persistent storage. The access token is kept
in memory by the client and is never written to `localStorage` or
`sessionStorage`.

Every access token carries a server-side session identifier (`sid`). The API
checks that the session is still active on every request, so logout, password
change and deactivation revoke access immediately instead of waiting for the
token to expire. Access tokens also carry `iss`, `aud`, `token_type` and `exp`
claims, which are all validated.

### Browser flow

1. `POST /api/v1/auth/login/` with a JSON username and password.
2. The response contains `access` and the safe user profile; `Set-Cookie` stores
   the refresh token as `HttpOnly`, `Secure` in production, `SameSite=Strict`
   in production (`Lax` in development) and scoped to `Path=/api/v1/auth/`.
   The same response sets a readable `csrftoken` cookie for cookie refresh.
3. Send `Authorization: Bearer <access>` to protected endpoints.
4. When the access token expires, call `POST /api/v1/auth/refresh/`. The browser
   sends the cookie automatically; the request must also echo the `csrftoken`
   cookie value in `X-CSRFToken`. A new access token is returned and the refresh
   cookie is replaced.
5. `POST /api/v1/auth/logout/` with the access token revokes every session for
   the caller and clears the refresh cookie.

Refresh tokens rotate on every use. A consumed token is rejected; presenting it
again is treated as reuse and revokes the whole token family (that login's
session chain), without touching the same user's other logins.

### CSRF model

CSRF protects **ambient cookie authority**, not explicit credentials:

- A refresh authorized by the `HttpOnly` cookie requires `X-CSRFToken`. Login
  sets the readable `csrftoken` cookie; the browser echoes that value in the
  header. There is no separate CSRF bootstrap endpoint.
- A refresh token supplied in the JSON body is an explicit credential chosen by
  the caller. It is not ambient, so it does not require CSRF. This is the path
  for CLI and server-to-server clients.
- Login is a JSON-only endpoint. Cross-site HTML forms cannot send
  `application/json` without a CORS preflight, and no permissive CORS policy is
  configured, so a cross-site form cannot drive a login. The login response also
  cannot be read cross-origin.
- Logout authenticates with a Bearer header, which a cross-site form cannot set.
  Bearer-only requests therefore need no CSRF token.
- Django admin keeps its own session cookie and Django CSRF protection. JWT
  cookies are never used for admin authentication.

`X-CSRFToken` is not a login requirement and is not needed for Bearer calls. It
is required only when the refresh token arrives in the cookie.

## Test with Swagger UI

The drf-spectacular schema and Swagger UI are served at:

- Schema: `http://127.0.0.1:8000/api/v1/schema/`
- Swagger UI: `http://127.0.0.1:8000/api/v1/docs/`

Development registers both routes and sets `API_DOCS_PUBLIC=true`, so the page
can be opened anonymously. Production keeps both routes staff-only and disabled
unless `ENABLE_API_DOCS=true`; `API_DOCS_PUBLIC` is forced to false there.

Swagger lists login, current user and logout. **`/api/v1/auth/refresh/` is
hidden from Swagger UI on purpose.** Hiding documentation does not disable the
endpoint: it remains fully operational for browser renewal and API clients. Its
contract is documented below and in
[frontend-integration.md](frontend-integration.md).

Exact browser steps:

1. Open the Swagger UI URL and expand **Authentication**.
2. `POST /api/v1/auth/login/` → **Execute** with
   `{"username": "your-username", "password": "your-password"}`. Expect `200`
   with `access` and `user`. The refresh cookie is set silently.
3. Click **Authorize**, paste only the `access` value and confirm. Swagger sends
   `Authorization: Bearer <access>` on subsequent operations.
4. `GET /api/v1/auth/me/` → **Execute**. Expect `200` with your user.
5. `POST /api/v1/auth/logout/` → **Execute**. Expect `200` and
   `{"message": "Logout successful. All active sessions for the current user have been revoked."}`.
6. `GET /api/v1/auth/me/` → **Execute** again. Expect `401 SESSION_REVOKED`.
7. **Authorize** → **Logout** to discard the old access token in the UI.

The documented success example for logout is a static contract example, not a
response captured from the running server.

### Exercise refresh through a separate API client

Refresh is intentionally absent from Swagger. Use curl or PowerShell with a
cookie jar:

```bash
# 1. Login and store the HttpOnly refresh cookie plus the readable CSRF cookie.
curl -s -c cookies.txt -H "Content-Type: application/json" \
  -d '{"username":"administrator","password":"your-password"}' \
  http://127.0.0.1:8000/api/v1/auth/login/

# 2. Refresh using the cookie plus X-CSRFToken read from the cookie jar.
CSRF=$(awk '$6 == "csrftoken" {print $7}' cookies.txt)
curl -s -b cookies.txt -c cookies.txt \
  -H "Content-Type: application/json" -H "X-CSRFToken: $CSRF" \
  -d '{}' http://127.0.0.1:8000/api/v1/auth/refresh/

# 3. Reusing the consumed cookie is rejected with 401.
```

CLI clients that do not keep cookies can send the refresh token in the body
instead, with no CSRF header:

```bash
curl -s -H "Content-Type: application/json" \
  -d '{"refresh":"<refresh-token>"}' \
  http://127.0.0.1:8000/api/v1/auth/refresh/
```

Non-browser clients receive the refresh token from their own credential store;
the API never returns it in JSON.

To keep local documentation staff-only, set `API_DOCS_PUBLIC=false` in
`backend/.env` and restart the server. This changes documentation visibility
only; it does not change API permissions.

## Endpoints

### `POST /api/v1/auth/login/`

Public. JSON only. No CSRF header is required (see “CSRF model”).

Request:

```json
{"username": "administrator", "password": "your-password"}
```

Success `200`:

```json
{
  "access": "<access-token>",
  "token_type": "Bearer",
  "expires_in": 300,
  "refresh_expires_in": 86400,
  "user": {
    "id": 1,
    "username": "administrator",
    "email": "admin@example.test",
    "first_name": "",
    "last_name": "",
    "is_staff": true,
    "roles": ["Administrator"],
    "permissions": ["accounts.manage_catalog", "accounts.manage_users"]
  }
}
```

The response also sets the refresh cookie:

```text
Set-Cookie: refresh_token=<token>; HttpOnly; Path=/api/v1/auth/; Max-Age=86400; SameSite=Strict; Secure
```

`Secure` and `SameSite=Strict` are used outside `DEBUG`; development uses
`SameSite=Lax` over plain HTTP.

It also sets the readable `csrftoken` cookie (`HttpOnly=False`, `SameSite=Lax`,
lifetime tied to the absolute session cap). The browser echoes that value in
`X-CSRFToken` on cookie-authorized refreshes.

Failures:

- `400 VALIDATION_ERROR` — missing/invalid fields or unexpected fields.
- `401 INVALID_CREDENTIALS` — wrong password, unknown user, inactive user, or
  any credential failure. The message is always
  `"Invalid username or password."`; account existence is not revealed.
- `429 RATE_LIMITED` — database-backed cooldown. `Retry-After` is in seconds.
- `413 PAYLOAD_TOO_LARGE` — body exceeds `MAX_JSON_BODY_BYTES`.
- `415 UNSUPPORTED_MEDIA_TYPE` — not `application/json`.

Login abuse protection defaults: 10 failures per username and 20 failures per
client IP within 15 minutes, followed by a 15-minute cooldown. Counters are
shared across processes through PostgreSQL. A successful login clears both
counters. Keys are HMAC-SHA256 hashes; raw usernames and IP addresses are not
stored in the throttle table. Refresh calls have a separate PostgreSQL-backed
limit.

### `POST /api/v1/auth/refresh/`

**Callable but hidden from Swagger UI.** Accepts either the `refresh_token`
cookie or a JSON `{"refresh": "<token>"}` body. Cookie refreshes require
`X-CSRFToken`; body refreshes do not.

Success `200` returns the same shape as login (a new `access`, `user`,
`token_type`, `expires_in`, `refresh_expires_in`) and sets a new refresh cookie.
No refresh token appears in the JSON body.

Failure behavior:

| Situation | Status | Code |
|---|---|---|
| Missing token | 401 | `INVALID_REFRESH_TOKEN` |
| Bad signature, expiry, issuer, audience or token type | 401 | `INVALID_REFRESH_TOKEN` |
| Cookie refresh without a valid CSRF token | 403 | `CSRF_FAILED` |
| Consumed refresh token replayed | 401 | `INVALID_REFRESH_TOKEN` or `REFRESH_REUSE_DETECTED` |
| Session revoked, expired or user inactive | 401 | `SESSION_REVOKED` |
| Refresh abuse limit reached | 429 | `RATE_LIMITED` |

Rotation is concurrency-safe: the session row is locked and only one request
can consume a given refresh JTI. Reuse detection revokes that login's token
family, so every token derived from the compromised chain stops working. Other
logins for the same user are unaffected.

### `POST /api/v1/auth/logout/`

Authenticated with the access token. No request body. Revokes **every** active
login session for the authenticated user (all access and refresh tokens) and
clears the refresh cookie with the same path and SameSite attributes used to set
it.

Success `200`:

```json
{"message": "Logout successful. All active sessions for the current user have been revoked."}
```

The response is `Cache-Control: no-store` and never `204`. Anonymous callers
receive `401`. A revocation failure returns `500 INTERNAL_ERROR` and never the
success message. Other users' sessions are not affected. Log in again to obtain
a new session.

### `GET /api/v1/auth/me/`

Authenticated. Returns the safe user object shown in the login response for the
caller only. There is no user-list endpoint. `PUT`, `PATCH` and `DELETE` return
`405 METHOD_NOT_ALLOWED`.

Access-token failures:

| Situation | Status | Code |
|---|---|---|
| Missing or malformed header | 401 | `UNAUTHENTICATED` / `TOKEN_INVALID` |
| Tampered, expired, wrong signature/issuer/audience/type | 401 | `TOKEN_INVALID` |
| Session revoked, expired or user inactive | 401 | `SESSION_REVOKED` |

### `GET /api/v1/health/live/`

Public liveness. Returns `200 {"status": "ok"}` while the process is serving.
Does not query PostgreSQL. Responses use `Cache-Control: no-store`.

### `GET /api/v1/health/ready/`

Public readiness. Executes a bounded PostgreSQL query with a statement timeout
(`HEALTH_DB_STATEMENT_TIMEOUT_MS`, default 2000 ms). Returns:

- `200 {"status": "ready"}`
- `503 {"status": "unavailable"}` with no database, host, user or exception
  details.

Responses use `Cache-Control: no-store`.

### Documentation and admin

- `GET /api/v1/schema/` — OpenAPI 3 schema. Refresh is excluded.
- `GET /api/v1/docs/` — Swagger UI.
- `GET /{ADMIN_URL}` — Django admin, staff users only, optionally restricted
  by `ADMIN_ALLOWED_IPS`, with Django's own session and CSRF protection.

In production both documentation routes require a staff user: `API_DOCS_PUBLIC`
is forced to false, and the routes exist only when `ENABLE_API_DOCS=true`. In
development `ENABLE_API_DOCS` defaults to true and `API_DOCS_PUBLIC` defaults to
true so login can be tested anonymously. Set `API_DOCS_PUBLIC=false` in
`backend/.env` and restart the server to require staff access locally. The admin
path is configurable and production rejects the default `admin/` path.

## Error envelope and codes

Every API error has exactly this top-level shape:

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "You do not have permission to perform this action.",
    "fields": {},
    "request_id": "a8d6f0e2b4c6a8d05f0c2d9a7b1e4c3a"
  }
}
```

`fields` maps field names to human-readable validation messages. Nested
serializer errors use dotted keys such as `profile.email`; serializer-wide
errors use `non_field_errors`. `request_id` always matches the `X-Request-ID`
response header. Clients may send a log-safe `X-Request-ID` (8–64 characters
from `A-Z a-z 0-9 . _ -`); invalid or missing values are replaced.

| Code | Typical status | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Request data failed validation |
| `INVALID_JSON` | 400 | Body is empty, malformed or not valid UTF-8 |
| `BAD_REQUEST` | 400 | Request rejected as unsafe/malformed |
| `INVALID_CREDENTIALS` | 401 | Generic login failure |
| `UNAUTHENTICATED` | 401 | Authentication required |
| `AUTHENTICATION_FAILED` | 401 | Authentication credentials rejected |
| `TOKEN_INVALID` | 401 | Access token failed signature, expiry, claim or type checks |
| `SESSION_REVOKED` | 401 | Token is valid but its server-side session is revoked/expired |
| `INVALID_REFRESH_TOKEN` | 401 | Refresh token invalid, expired, wrong type or already consumed |
| `REFRESH_REUSE_DETECTED` | 401 | Refresh replay detected; the token family was revoked |
| `CSRF_FAILED` | 403 | CSRF verification failed |
| `FORBIDDEN` | 403 | Authenticated but not authorized |
| `NOT_FOUND` | 404 | No matching resource/route |
| `METHOD_NOT_ALLOWED` | 405 | Method not supported by the route |
| `NOT_ACCEPTABLE` | 406 | Requested response format unavailable |
| `PAYLOAD_TOO_LARGE` | 413 | Body exceeds configured limit |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Content-Type is not JSON |
| `RATE_LIMITED` | 429 | Login/refresh cooldown or throttling |
| `API_ERROR` | varies | Safe fallback for an API exception |
| `INTERNAL_ERROR` | 500 | Unexpected failure; details stay in server logs |

Authentication failures carry `WWW-Authenticate: Bearer`; `429` responses carry
`Retry-After`. Unexpected exceptions never return tracebacks, SQL, credentials
or exception text.

## PowerShell examples

```powershell
$base = "http://127.0.0.1:8000"
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

$loginBody = @{
    username = "administrator"
    password = "your-password"
} | ConvertTo-Json

$login = Invoke-RestMethod "$base/api/v1/auth/login/" `
    -Method Post `
    -WebSession $session `
    -ContentType "application/json" `
    -Body $loginBody

$access = $login.access
$headers = @{ Authorization = "Bearer $access" }

Invoke-RestMethod "$base/api/v1/auth/me/" -WebSession $session -Headers $headers

# Refresh: the HttpOnly cookie is in $session; CSRF is required for cookie use.
$csrf = $session.Cookies.GetCookies($base)["csrftoken"].Value
$refreshHeaders = @{ "X-CSRFToken" = $csrf }

$refreshed = Invoke-RestMethod "$base/api/v1/auth/refresh/" `
    -Method Post `
    -WebSession $session `
    -ContentType "application/json" `
    -Headers $refreshHeaders `
    -Body "{}"

$access = $refreshed.access

$logout = Invoke-RestMethod "$base/api/v1/auth/logout/" `
    -Method Post `
    -WebSession $session `
    -Headers @{ Authorization = "Bearer $access" }

$logout.message
# Logout successful. All active sessions for the current user have been revoked.

# The old access and refresh credentials are now rejected.
```

## HTTP status conventions

- `200` for successful reads, login, refresh and logout.
- `400` for validation, parse and malformed-request failures.
- `401` for missing/invalid authentication and token or session failures.
- `403` for CSRF failures and authenticated authorization failures.
- `404` for unknown API routes.
- `405` for unsupported methods.
- `413`/`415` for body size and media-type failures.
- `429` for login or refresh cooldown.
- `500` for unexpected server failures with a generic envelope.
- `503` only for readiness when PostgreSQL is unavailable.

There is no `204` response in the authentication API; logout returns a JSON
body so clients can confirm what was revoked.
