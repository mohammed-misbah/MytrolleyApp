# Frontend Integration — JWT Authentication

This note is for the React/iOS clients that consume the MyTrolley API. It
documents the browser contract for access and refresh tokens. The API is
same-origin; there is no permissive CORS configuration, so the browser sends
cookies only to the origin that served the app.

## What the client receives

Login `POST /api/v1/auth/login/`:

```json
{
  "access": "<short-lived access token>",
  "token_type": "Bearer",
  "expires_in": 300,
  "refresh_expires_in": 86400,
  "user": {"id": 1, "username": "administrator", "roles": ["Administrator"]}
}
```

The refresh token is **not** in this JSON. It arrives as a `Set-Cookie` header:

```text
refresh_token=<token>; HttpOnly; Path=/api/v1/auth/; Max-Age=86400;
SameSite=Strict; Secure
```

The cookie is `HttpOnly` (page script cannot read it), `Secure` outside
development, and `SameSite=Strict` in production (`Lax` in development so
plain-HTTP localhost works). It is scoped to `/api/v1/auth/`, so it is only sent
to login, refresh and logout calls.

Login also sets a readable `csrftoken` cookie. That value is not an
authentication secret; the browser echoes it in `X-CSRFToken` when refresh uses
the ambient cookie.

## Storage rules

| Item | Where it may live | Where it must not live |
|---|---|---|
| Access token | JavaScript memory (module variable, React state, auth context) | `localStorage`, `sessionStorage`, IndexedDB, cookies, URLs, logs |
| Refresh token | Only the server-set `HttpOnly` cookie | Any JavaScript-readable storage; never parse or copy it |
| User profile | Memory; it is safe to keep in app state | Persistent storage containing tokens |

On a full page reload the in-memory access token is gone. Restore the session by
calling refresh once; if it succeeds, the user is still logged in. If it fails
with `401`, show the login screen. Do not keep an access token in a cookie “for
convenience”: that reintroduces CSRF and XSS exposure the design avoids.

## API client behavior

1. Attach `Authorization: Bearer <access>` to every protected request.
2. Send `Content-Type: application/json` on writes.
3. Send cookies on auth calls (`credentials: "same-origin"`; same-origin
   requests include them by default).
4. On `401 TOKEN_INVALID` (expired/invalid access), refresh once, replace the
   access token, then retry the original request once.
5. On `401 SESSION_REVOKED` or a failed refresh, clear the access token and send
   the user to login. Retrying cannot help.
6. Never retry a refresh request automatically in a loop.

### Serialize refresh requests

Refresh tokens rotate. Two parallel refreshes with the same token look like
reuse: one consumes it, the other is treated as a replay and the whole token
family is revoked. The API serializes the database work, but the client must
still ensure **at most one refresh is in flight**.

Use a single shared promise and queue callers behind it:

```ts
// src/auth/tokenStore.ts
import { getCsrfToken } from "./csrf";

let accessToken: string | null = null;
let refreshInFlight: Promise<string> | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

async function requestRefresh(): Promise<string> {
  // The refresh cookie is HttpOnly; the body is empty on purpose.
  const csrf = getCsrfToken();
  if (!csrf) {
    accessToken = null;
    throw new Error("missing csrf cookie; log in again");
  }

  const response = await fetch("/api/v1/auth/refresh/", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrf,
    },
    body: "{}",
  });

  if (!response.ok) {
    accessToken = null;
    throw new Error(`refresh failed: ${response.status}`);
  }

  const body = (await response.json()) as { access: string };
  accessToken = body.access;
  return body.access;
}

export function refreshAccessToken(): Promise<string> {
  // Single-flight: every caller shares one network request.
  refreshInFlight ??= requestRefresh().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}
```

### CSRF for cookie refresh

Cookie-authorized refresh requires `X-CSRFToken`. Login already set the readable
`csrftoken` cookie, so read it directly; there is no bootstrap request:

```ts
// src/auth/csrf.ts
export function getCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}
```

Do not try to read the `refresh_token` cookie. If `csrftoken` is missing, the
session cannot be renewed from the browser; show the login screen. After a
`403 CSRF_FAILED` with a present cookie, reload the app once so a fresh page can
pick up the current cookie; do not retry in a loop.

### Fetch wrapper with one retry

```ts
export async function apiFetch(
  path: string,
  init: RequestInit = {},
  retried = false,
): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");

  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "same-origin",
  });

  if (response.status !== 401 || retried) return response;

  const body = await response.clone().json().catch(() => null);
  const code = body?.error?.code;

  // A revoked session cannot be repaired by refreshing.
  if (code === "SESSION_REVOKED") {
    setAccessToken(null);
    return response;
  }

  try {
    await refreshAccessToken();
  } catch {
    return response;
  }
  return apiFetch(path, init, true);
}
```

Do not refresh on `401 INVALID_CREDENTIALS` (login) or on a failed refresh
itself.

## Login

```ts
export async function login(username: string, password: string) {
  const response = await fetch("/api/v1/auth/login/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message ?? "Login failed");
  }

  const body = await response.json();
  setAccessToken(body.access);
  return body.user;
}
```

Login does not need `X-CSRFToken`: it is a JSON-only request with explicit
credentials, and the response is unreadable cross-origin. The CSRF requirement
applies when the browser authenticates with the ambient refresh cookie. A
successful login sets both the `refresh_token` and `csrftoken` cookies.

## Logout

```ts
export async function logout(): Promise<void> {
  const token = getAccessToken();
  try {
    if (token) {
      await fetch("/api/v1/auth/logout/", {
        method: "POST",
        credentials: "same-origin",
        headers: { Authorization: `Bearer ${token}` },
      });
    }
  } finally {
    setAccessToken(null);
    // Clear any app state derived from the user profile.
  }
}
```

The API revokes **all** sessions for the current user, not just the current tab.
It returns `200` with:

```json
{"message": "Logout successful. All active sessions for the current user have been revoked."}
```

If logout returns `401`, the token was already invalid; clear local state
anyway. If it returns `500`, do not claim success in the UI: show an error and
keep the user informed that the server could not confirm revocation.

## Token lifetime and renewal timing

Defaults: access 300 seconds, refresh 86,400 seconds, absolute session 604,800
seconds. Values come from `JWT_ACCESS_TOKEN_LIFETIME_SECONDS`,
`JWT_REFRESH_TOKEN_LIFETIME_SECONDS` and `JWT_ABSOLUTE_SESSION_SECONDS` in
`backend/.env`. Rotation never extends the absolute session limit; after it
expires the user must log in again.

Refresh reactively on `401`, or proactively shortly before `expires_in` runs
out. Either way, keep the single-flight guarantee. Do not schedule one refresh
per open tab.

## Refresh is hidden from Swagger, not disabled

`POST /api/v1/auth/refresh/` is excluded from Swagger UI and the public schema,
but it is fully operational. Use the client above, curl, or PowerShell. Its
contract is also documented in [api.md](api.md#post-apiv1authrefresh).

## Security notes and limits

- The access token is bearer-only. Anyone who obtains it can act as the user
  until it expires or its session is revoked. Never log it, put it in a URL,
  send it to analytics, or persist it.
- XSS can still call the API as the logged-in user even though it cannot read
  the refresh cookie. A restrictive Content-Security-Policy and output encoding
  are required at the frontend/proxy layer; they are not implemented in Django.
- Do not add permissive CORS with credentials. The cookie design assumes a
  same-origin deployment.
- Hiding refresh from Swagger is a documentation choice, not a security control.
- Passing tests does not prove the frontend is free of token leaks; review the
  client code and browser storage during implementation.
