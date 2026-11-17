# API Contract — Milestone 1

Base path: `/api/v1`. All request and response bodies are JSON; the API parser
accepts only `application/json` and the renderer returns JSON. There is no CORS
configuration because the assessment assumes a same-origin deployment (for
example, the React build served by the same reverse proxy as Django).

## CSRF and session flow

Authentication uses Django database sessions. The session cookie is
`HttpOnly`, `SameSite=Lax`, and expires after 8 hours of inactivity
(`SESSION_SAVE_EVERY_REQUEST=True`). The CSRF cookie must be readable by the
browser because the client copies it into the `X-CSRFToken` header.

1. `GET /api/v1/auth/csrf/` sets the `csrftoken` cookie and returns a masked
   token in `csrfToken`. The response is `Cache-Control: no-store`.
2. Send the token in `X-CSRFToken` on login. Login is explicitly wrapped in
   Django's `csrf_protect` because DRF session authentication does not enforce
   CSRF for anonymous requests.
3. A successful login rotates the session ID and the CSRF token. Discard the
   old token and re-fetch `/api/v1/auth/csrf/` (or read the new cookie) before
   the next unsafe request.
4. Every authenticated unsafe request must include `X-CSRFToken`.
5. Logout flushes the server-side session, rotates the CSRF token and returns
   `204`. Re-fetch the bootstrap before logging in again.

Login, logout and `me` responses use `Cache-Control: no-store`.

## Test with Swagger UI

The existing drf-spectacular schema and Swagger UI are served at:

- Schema: `http://127.0.0.1:8000/api/v1/schema/`
- Swagger UI: `http://127.0.0.1:8000/api/v1/docs/`

Development registers both routes and sets `API_DOCS_PUBLIC=true`, so the page
can be opened anonymously and the login flow tested without first using Django
admin. Production keeps both routes staff-only and disabled unless
`ENABLE_API_DOCS=true`; `API_DOCS_PUBLIC` is forced to false there.

The project overrides drf-spectacular's Swagger script with
`backend/core/templates/core/swagger_ui.js`. That script:

- fetches `/api/v1/auth/csrf/` once on page load;
- reads the current `csrftoken` cookie for every unsafe request and sets
  `X-CSRFToken`, replacing any value already present under different casing;
- fills the documented required `X-CSRFToken` field so Swagger UI validation
  passes without manual copying;
- re-reads the cookie after every response, covering login and logout rotation.

Exact browser steps:

1. Open the Swagger UI URL and expand **Authentication**.
2. `GET /api/v1/auth/csrf/` → **Execute**. Expect `200` and a `csrfToken` body.
3. `POST /api/v1/auth/login/` → **Execute** with
   `{"username": "your-username", "password": "your-password"}`. Expect `200`.
4. `GET /api/v1/auth/me/` → **Execute**. Expect `200` with your user.
5. `POST /api/v1/auth/logout/` → **Execute**. Expect `204`.
6. `GET /api/v1/auth/me/` → **Execute** again. Expect `401 UNAUTHENTICATED`.

If JavaScript is disabled or the script fails to load, paste the `csrfToken`
from step 2 (or the `csrftoken` cookie value) into the `X-CSRFToken` field
before each unsafe request, and repeat step 2 after login and logout. The
returned masked token and the cookie value are both accepted; they are not
expected to be identical.

To keep local documentation staff-only, set `API_DOCS_PUBLIC=false` in
`backend/.env` and restart the server. This changes documentation visibility
only; it does not change API permissions or disable CSRF.

## Endpoints

### `GET /api/v1/auth/csrf/`

Public. No authentication, no CSRF token required.

```json
{"csrfToken": "masked-csrf-token"}
```

Sets `csrftoken` (HttpOnly false, SameSite=Lax). The returned masked token and
the cookie value are both accepted as the `X-CSRFToken` value.

### `POST /api/v1/auth/login/`

Public, but requires a matching `csrftoken` cookie and `X-CSRFToken` header.

Request:

```json
{"username": "administrator", "password": "your-password"}
```

Success `200`:

```json
{
  "id": 1,
  "username": "administrator",
  "email": "admin@example.test",
  "first_name": "",
  "last_name": "",
  "is_staff": true,
  "roles": ["Administrator"],
  "permissions": ["accounts.manage_catalog", "accounts.manage_users"]
}
```

Failures:

- `400 VALIDATION_ERROR` — missing/invalid fields or unexpected fields.
- `401 INVALID_CREDENTIALS` — wrong password, unknown user, inactive user, or
  any credential failure. The message is always
  `"Invalid username or password."`; account existence is not revealed.
- `403 CSRF_FAILED` — missing, invalid or origin-mismatched CSRF token.
- `429 RATE_LIMITED` — database-backed cooldown. `Retry-After` is in seconds.
- `413 PAYLOAD_TOO_LARGE` — body exceeds `MAX_JSON_BODY_BYTES`.
- `415 UNSUPPORTED_MEDIA_TYPE` — not `application/json`.

Abuse protection defaults: 10 failures per username and 20 failures per client
IP within 15 minutes, followed by a 15-minute cooldown. Counters are shared
across processes through PostgreSQL. A successful login clears both counters.
Keys are HMAC-SHA256 hashes; raw usernames and IP addresses are not stored in
the throttle table.

### `POST /api/v1/auth/logout/`

Authenticated and CSRF-protected. Success is `204 No Content`. The server-side
session row is deleted; a later `GET /me/` returns `401 UNAUTHENTICATED`.
Anonymous callers receive `401`, not `403`, so clients can distinguish missing
authentication from insufficient permission.

### `GET /api/v1/auth/me/`

Authenticated. Returns the same safe shape as the login success response for
the caller only. There is no user-list endpoint. `PUT`, `PATCH` and `DELETE`
return `405 METHOD_NOT_ALLOWED`.

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

- `GET /api/v1/schema/` — OpenAPI 3 schema.
- `GET /api/v1/docs/` — Swagger UI.
- `GET /{ADMIN_URL}` — Django admin, staff users only, optionally restricted
  by `ADMIN_ALLOWED_IPS`.

In production both documentation routes require a staff user: `API_DOCS_PUBLIC`
is forced to false, and the routes exist only when `ENABLE_API_DOCS=true`. In
development `ENABLE_API_DOCS` defaults to true and `API_DOCS_PUBLIC` defaults to
true so the anonymous login flow can be tested. Set `API_DOCS_PUBLIC=false` in
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
| `CSRF_FAILED` | 403 | CSRF verification failed |
| `FORBIDDEN` | 403 | Authenticated but not authorized |
| `NOT_FOUND` | 404 | No matching resource/route |
| `METHOD_NOT_ALLOWED` | 405 | Method not supported by the route |
| `NOT_ACCEPTABLE` | 406 | Requested response format unavailable |
| `PAYLOAD_TOO_LARGE` | 413 | Body exceeds configured limit |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Content-Type is not JSON |
| `RATE_LIMITED` | 429 | Login cooldown or throttling |
| `API_ERROR` | varies | Safe fallback for an API exception |
| `INTERNAL_ERROR` | 500 | Unexpected failure; details stay in server logs |

`413`, `429` and authentication responses may include `Retry-After` or
`WWW-Authenticate` headers. Unexpected exceptions never return tracebacks, SQL,
credentials or exception text.

## PowerShell examples

```powershell
$base = "http://127.0.0.1:8000"
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

$csrf = Invoke-RestMethod "$base/api/v1/auth/csrf/" -WebSession $session

$loginBody = @{
    username = "administrator"
    password = "your-password"
} | ConvertTo-Json

$me = Invoke-RestMethod "$base/api/v1/auth/login/" `
    -Method Post `
    -WebSession $session `
    -ContentType "application/json" `
    -Headers @{ "X-CSRFToken" = $csrf.csrfToken } `
    -Body $loginBody

$me | ConvertTo-Json -Depth 5

# Re-fetch after login because the CSRF token rotated.
$csrf = Invoke-RestMethod "$base/api/v1/auth/csrf/" -WebSession $session

Invoke-RestMethod "$base/api/v1/auth/logout/" `
    -Method Post `
    -WebSession $session `
    -ContentType "application/json" `
    -Headers @{ "X-CSRFToken" = $csrf.csrfToken } `
    -Body "{}"
```

## HTTP status conventions

- `200` for successful reads/logins.
- `204` for successful logout.
- `400` for validation, parse and malformed-request failures.
- `401` when authentication is missing or credentials are invalid.
- `403` for CSRF failures and authenticated authorization failures.
- `404` for unknown API routes.
- `405` for unsupported methods.
- `413`/`415` for body size and media-type failures.
- `429` for login cooldown.
- `500` for unexpected server failures with a generic envelope.
- `503` only for readiness when PostgreSQL is unavailable.
