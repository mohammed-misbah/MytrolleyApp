# Security — Milestone 1

## Security objectives

Milestone 1 protects account credentials, sessions, role assignments and the
operational surface of the API. The design prioritises:

1. **No default access:** no default account, no public registration and
   default-deny API permissions.
2. **Revocable token authentication:** short-lived JWT access tokens backed by
   server-side auth sessions, plus rotating refresh tokens delivered in an
   HttpOnly cookie with CSRF protection on cookie-authorized renewal.
3. **Least privilege:** two explicit business permissions, enforced server-side.
4. **Fail closed:** invalid production configuration stops startup rather than
   silently downgrading security.
5. **No secret or internal-detail leakage:** generic client errors, allowlisted
   structured logs, guidance-only validation failures.
6. **Shared abuse resistance:** login throttling works across processes without
   relying on process-local memory or Redis.

## Assets and actors

| Asset | Why it matters |
|---|---|
| User credentials and password hashes | Account takeover |
| JWT access tokens | Authenticated access without a password until expiry/revocation |
| Refresh tokens and auth sessions | Long-lived authenticated access and renewal |
| JWT signing key, `DJANGO_SECRET_KEY` and database credentials | Token forgery or full data/system compromise |
| CSRF tokens | Protection against cross-site cookie-authorized state changes |
| Role/group/permission assignments | Business authorization and escalation |
| Audit/log data | Detection, correlation and incident response |
| Admin and API documentation | High-value reconnaissance/administration surface |

Actors: anonymous internet client, authenticated ungrouped user, DataEntry user,
Administrator, staff operator, reverse proxy, database, CI, and a future object
storage service. All client input is untrusted.

## Trust boundaries

See [architecture.md](architecture.md#trust-boundaries) for the diagram. The
most important assumptions are:

- TLS terminates at a controlled reverse proxy in production; Django is not
  exposed directly to the internet.
- The browser, React app and API share one origin. There is no permissive CORS
  configuration.
- `X-Forwarded-*` headers are trusted only when `TRUST_PROXY_HEADERS=true`, and
  only because the proxy is expected to overwrite them.
- PostgreSQL is reached over a private network with TLS in production. The
  application database role is not a PostgreSQL superuser.
- Production secrets live outside the repository and outside logs.

## Authentication and session controls

- **Custom user before first migration.** `AUTH_USER_MODEL = "accounts.User"` is
  set before `accounts/migrations/0001_initial.py`; the user has a unique email.
- **No default credentials.** Migrations create no user. The only provisioning
  path is `create_initial_admin`, which prompts with `getpass` and refuses
  command-line passwords.
- **No registration endpoint.** `/api/v1/auth/register/` returns `404`; there is
  no self-service account creation.
- **Token pair.** `POST /api/v1/auth/login/` issues a short-lived JWT access
  token (default 300 seconds) and creates a server-side `AuthSession` row. The
  response contains only the access token and safe profile; the refresh token is
  delivered as an `HttpOnly` cookie.
- **Session-backed revocation.** Every access token carries a `sid` claim. The
  authentication class requires the referenced `AuthSession` to be active, so
  logout, password change and deactivation take effect immediately rather than
  waiting for the access token to expire.
- **Claim validation.** Tokens are signed with a dedicated
  `JWT_SIGNING_KEY`, are accepted only with `HS256`, and are validated for
  signature, expiry, issuer, audience and token type. Access tokens cannot be
  used as refresh tokens, and vice versa.
- **Refresh rotation.** Refresh tokens carry a JTI and a family ID. Each refresh
  locks the session row, checks the stored JTI and issues a new pair. A consumed
  JTI presented again is treated as reuse: the affected token family is revoked
  and the request fails. Other logins for the same user are not revoked.
- **Absolute expiry.** `AuthSession.expires_at` is a hard limit (default 7
  days). A rotated refresh token lifetime is capped at that expiry, so renewal
  can never extend the session indefinitely.
- **Cookie flags.** `refresh_token` is `HttpOnly`, `Secure` outside development,
  `SameSite=Strict` outside development (`Lax` locally), scoped to
  `Path=/api/v1/auth/`, with a max-age equal to the refresh lifetime. Logout
  clears it with matching path/SameSite attributes.
- **Logout.** `POST /api/v1/auth/logout/` revokes every active auth session for
  the caller, clears the refresh cookie and returns `200` with an explicit
  message. Access and refresh tokens for all of that user's logins stop working
  immediately. The endpoint never returns a success message when authentication
  or revocation fails.
- **Inactive users.** Django's authentication backend rejects inactive users at
  login; an existing session for a user later marked inactive is rejected by
  the authentication class and revoked by the user save signal.
- **Generic failures.** Wrong password, unknown user and inactive user all
  return the same `401 INVALID_CREDENTIALS` message. The response never reveals
  whether the account exists.
- **Browser storage.** The access token is kept in memory only; the refresh
  token is unreadable by page script. Neither token is written to
  `localStorage` or `sessionStorage`.

Django's database-backed `sessionid` cookie remains in use for the Django admin
only. Admin CSRF and session rotation are unchanged and independent of the JWT
API.

## CSRF design

CSRF protection applies to state changes authorized by an **ambient cookie**.
The JWT API has exactly one such credential: the `refresh_token` cookie.

- `POST /api/v1/auth/refresh/` requires `X-CSRFToken` when the refresh token is
  read from the cookie. The check uses Django's `CsrfViewMiddleware` against the
  real request, so origin, referer and token validation behave like Django's.
- A refresh token supplied in the JSON body is an explicit credential chosen by
  the caller, not an ambient cookie, so it does not require CSRF. This keeps
  CLI and server-to-server renewal usable.
- Login uses `ensure_csrf_cookie`, so a successful login sets the readable
  `csrftoken` cookie. The browser echoes that value in `X-CSRFToken` on cookie
  refresh. There is no public CSRF bootstrap endpoint.
- Login is JSON-only and credential-based. A cross-site HTML form cannot send
  `application/json` without a CORS preflight, no permissive CORS policy exists,
  and the response is unreadable cross-origin. Login therefore does not accept
  `X-CSRFToken` as a substitute for credentials and does not require the header.
- Logout authenticates with `Authorization: Bearer`, a header a cross-site form
  cannot set and a cookie the browser does not attach automatically for API
  authorization. Bearer-only requests need no CSRF token.
- `CSRF_COOKIE_HTTPONLY=False` because the browser must copy the value into
  `X-CSRFToken`. The cookie is not an authentication secret by itself; the
  refresh cookie remains `HttpOnly`.
- `CSRF_COOKIE_SAMESITE="Lax"`, `CSRF_USE_SESSIONS=False`, and
  `CSRF_COOKIE_AGE = JWT_ABSOLUTE_SESSION_SECONDS` so an idle browser can still
  refresh within the hard session cap.
- `CSRF_TRUSTED_ORIGINS` accepts only exact `scheme://host[:port]` origins; the
  parser rejects wildcards, credentials, paths, queries and fragments.
- A CSRF failure on `/api/` returns the JSON envelope with `CSRF_FAILED`; the
  admin keeps Django's HTML 403 page.
- There is no CORS package. A same-origin deployment keeps the cookie/CSRF model
  simple and avoids cross-origin credential exposure.

Hiding refresh from Swagger UI is a documentation choice, not a CSRF or
authorization control. The endpoint remains callable and protected as above.

## Authorization model

`REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]` is
`IsAuthenticated`. Public endpoints opt out individually:

- `POST /api/v1/auth/login/` (JSON-only credential exchange)
- `POST /api/v1/auth/refresh/` (hidden from Swagger; CSRF when cookie-authorized)
- `GET /api/v1/health/live/`
- `GET /api/v1/health/ready/`

Everything else is authenticated by default. Business operations additionally
require a codename through `HasBusinessPermission`:

| Role | Group | Permissions |
|---|---|---|
| Administrator | `Administrator` | `accounts.manage_users`, `accounts.manage_catalog` |
| Data-entry | `DataEntry` | `accounts.manage_catalog` |
| Ungrouped authenticated | — | none |

Seeding is declarative and idempotent: every run leaves each group with exactly
the configured permission set. It is invoked by `post_migrate` for the
`accounts` app and by the `seed_roles` management command.

### Escalation resistance

- Login accepts only `username` and `password` through `StrictSerializer`;
  unknown fields such as `is_staff`, `groups` or `permissions` produce
  `VALIDATION_ERROR` instead of being silently ignored.
- `/me/` is read-only; `PUT`, `PATCH` and `DELETE` return `405`.
- The user response exposes only `id`, `username`, `email`, `first_name`,
  `last_name`, `is_staff`, role names and the two business permissions. It does
  not expose password hashes, session identifiers or the full permission set.
- Staff status alone does not grant business permissions; a staff user without
  a role is still forbidden (tested).
- There are no user-management endpoints in milestone 1. Future endpoints must
  reuse the strict serializer and permission class, and must audit privileged
  changes.

## Login abuse protection

`accounts.LoginThrottle` is a PostgreSQL table, so limits apply across every
application process and survive process restarts.

- **Default limits:** 10 failures per username and 20 per client IP in a
  15-minute window, then a 15-minute cooldown (`Retry-After` on `429`).
- **Keys:** HMAC-SHA256 over a versioned context, scope and normalized value,
  keyed by `DJANGO_SECRET_KEY`. Raw usernames and IP addresses are not stored.
- **Normalization:** usernames are stripped and case-folded, so case variants
  share a counter.
- **Atomic updates:** failures run in a transaction with
  `select_for_update()` per key; a unique `key_hash` prevents duplicate rows.
- **Recovery:** a successful login deletes both counters. Expired windows and
  cooldowns reset on the next failure. `prune_login_throttles --days N` removes
  stale non-blocking rows.
- **Privacy:** because keys are HMACs, the table can still be correlated by
  someone with the application secret, but it does not directly reveal
  usernames/IPs in backups or ad-hoc queries.
- **Operational note:** rotating `DJANGO_SECRET_KEY` makes existing throttle
  keys unreachable; prune the table after a key rotation. Rotating
  `JWT_SIGNING_KEY` invalidates every JWT access and refresh token immediately,
  so schedule it in a maintenance window.
- **Refresh abuse:** `accounts.RefreshThrottle` uses the same keyed-hash design
  for refresh attempts (default 120 per user and 300 per IP in a 15-minute
  window, then a 15-minute cooldown). A successful login clears the caller's
  refresh counters. The refresh endpoint is hidden from Swagger but is still
  rate-limited.

Throttling is not a substitute for strong passwords, MFA or network controls.
Distributed password spraying across many IPs remains partially possible; the
per-username limit is the primary mitigation.

## Input handling and request limits

- JSON-only parser and renderer; form posts return `415`.
- `BoundedJSONParser` checks `Content-Length` before reading and reads at most
  `MAX_JSON_BODY_BYTES + 1`, returning `413 PAYLOAD_TOO_LARGE` without echoing
  the body.
- `DATA_UPLOAD_MAX_MEMORY_SIZE` 262,144 bytes, `DATA_UPLOAD_MAX_NUMBER_FIELDS`
  100, `DATA_UPLOAD_MAX_NUMBER_FILES` 10, upload permissions `0640`/`0750`.
- All request bodies/queries must be validated with zod-equivalent DRF
  serializers; login uses explicit `max_length` bounds and rejects unknown
  fields.
- `APPEND_SLASH=False` keeps API routes explicit and avoids redirect-based
  method/body surprises.
- `X-Request-ID` accepts only 8–64 characters from `A-Z a-z 0-9 . _ -`;
  anything else is replaced with a cryptographically random ID.

## Error handling and logging

Every API error uses one envelope: `code`, `message`, `fields`, `request_id`.
The request ID is echoed in `X-Request-ID`.

- Validation messages are returned per field; internal exception strings are
  not.
- Malformed JSON returns a generic `INVALID_JSON`; parser details such as
  `json.decoder` or `Expecting` are suppressed.
- Unexpected exceptions return `500 INTERNAL_ERROR` and are logged with a
  traceback, request ID, method and path. SQL, credentials, request bodies and
  cookies are not logged.
- `JsonFormatter` serializes an allowlist of operational fields (`event`,
  `method`, `path`, `status`, `duration_ms`, `reason`, `retry_after`,
  `user_id`, `error_type`) plus the exception traceback. Arbitrary `extra`
  attributes, including a test `password`, are dropped.
- Login, refresh and logout successes/failures and CSRF failures are logged as
  events without submitted passwords, usernames, access/refresh tokens,
  `Authorization` headers or cookie values.
- Readiness failures log only the exception class, never the driver message.

## Production configuration and secrets

`config.settings.production` validates configuration at startup and fails
closed with variable names only:

- `DEBUG` false.
- `DJANGO_SECRET_KEY` at least 50 characters, not a known placeholder, with
  sufficient variation.
- `JWT_SIGNING_KEY` at least 50 characters and different from
  `DJANGO_SECRET_KEY`; only the variable name is shown on failure.
- Explicit `DJANGO_ALLOWED_HOSTS`; `*` is rejected.
- `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` true.
- Refresh cookies use `Secure` and `SameSite=Strict` because `DEBUG` is false.
- `SECURE_SSL_REDIRECT` true.
- HSTS configured with a non-negative value; preload requires subdomains and at
  least one year.
- `DB_SSLMODE` one of `require`, `verify-ca`, `verify-full`; CA required for the
  verifying modes.
- Non-default `ADMIN_URL`.
- Exact HTTPS `CSRF_TRUSTED_ORIGINS`, no wildcards.
- Proxy trust only with a configured `SECURE_PROXY_SSL_HEADER`.

`backend/.env` is gitignored; `backend/.env.example` contains placeholders only.
Real process environment variables take precedence over the file. The project
does not print secret values on validation failure.

## Security headers and transport

Base settings set:

- `SECURE_CONTENT_TYPE_NOSNIFF=True`
- `X_FRAME_OPTIONS="DENY"`
- `SECURE_REFERRER_POLICY="same-origin"`
- `SECURE_CROSS_ORIGIN_OPENER_POLICY="same-origin"`

Production adds:

- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`
- `SECURE_HSTS_SECONDS` from explicit configuration, optional subdomains/preload

There is **no Content-Security-Policy** in Django itself. A production reverse
proxy or the future React hosting layer should add a restrictive CSP. This is a
known milestone-1 gap, not an implicit claim of complete browser hardening.

## Admin and documentation exposure

- Django admin is staff-only by Django's own permission checks.
- `ADMIN_ALLOWED_IPS` optionally restricts admin paths by exact IP/CIDR; invalid
  entries fail configuration parsing.
- The admin URL is configurable; production rejects the default `admin/` path.
- OpenAPI schema and Swagger UI require `IsAdminUser` (staff) in production.
- Documentation URLs are registered only when `ENABLE_API_DOCS=true`.
  Development enables them; production defaults to disabled.
- `API_DOCS_PUBLIC` defaults to false. Development may set it to true so the
  docs can be opened anonymously for login testing; production forces it to
  false. This flag changes documentation visibility only, not API permissions
  or CSRF enforcement.
- Swagger UI uses drf-spectacular's stock template. There is no project CSRF
  bootstrap script and no CSRF parameter in the schema; Bearer calls need none.
- `POST /api/v1/auth/refresh/` is excluded from the public schema and Swagger UI.
  The route stays callable; hiding it is documentation policy, not a security
  control.
- Documentation error responses are forced through the JSON renderer so the
  error contract stays consistent even on drf-spectacular views.

## Health endpoint security

- `/live/` performs no database query and never fails because PostgreSQL is
  down.
- `/ready/` runs `SELECT 1` inside a transaction with a bounded statement
  timeout. It returns a generic `503 {"status": "unavailable"}` and logs only
  the exception class.
- Both responses use `Cache-Control: no-store` and expose no version, host,
  user or driver details.
- Both are intentionally public so load balancers can probe them.

## Supply chain and CI

- Runtime and development dependencies are pinned in
  `backend/requirements/`.
- Ruff, mypy, pytest, coverage, drf-spectacular validation and `pip-audit` run
  in CI.
- CI uses ephemeral PostgreSQL credentials and a test-only signing key.
- `pip-audit` currently reports no known vulnerabilities for runtime or
  development requirements (pytest was updated to 9.0.3 for PYSEC-2026-1845).
- Migrations are committed; CI checks for schema drift with
  `makemigrations --check --dry-run`.

## Residual risks and accepted trade-offs

| Risk | Status / mitigation |
|---|---|
| No MFA or password-reset flow | Out of milestone 1 scope; required before production exposure |
| XSS can act as the user despite HttpOnly | No CSP yet; future frontend/proxy must add CSP and output encoding |
| Access-token theft via compromised browser | Short 5-minute lifetime plus session revocation on logout/password change/deactivation; a stolen access token works until then |
| Refresh-cookie theft | HttpOnly/Secure/SameSite cookie, rotation on every use, reuse detection revokes the family, absolute 7-day session limit |
| Refresh replay by a parallel client | Server-side row lock and JTI rotation; clients must serialize refresh calls (documented in `docs/frontend-integration.md`) |
| Secret rotation breaks sessions/throttle keys | Rotating `JWT_SIGNING_KEY` invalidates all JWT sessions; rotating `DJANGO_SECRET_KEY` breaks throttle keys and admin sessions. Rotate during a maintenance window and prune stale rows |
| Distributed password spraying | Per-username and per-IP DB limits reduce but do not eliminate |
| Throttle table growth | `prune_login_throttles` and `prune_jwt_tokens` commands; schedule them operationally |
| OneDrive-synced workspace | `backend/.env` is gitignored but may still sync to cloud storage; keep production secrets out of synced local files |
| Public development docs | Development defaults to anonymous docs so a fresh login can be tested; bind the dev server to localhost and set `API_DOCS_PUBLIC=false` if that exposure is unwanted |
| No malware scanning for future images | Explicitly deferred to milestone 3; design requires validation, re-encoding and scanning |
| Admin depends on staff flag | Staff is necessary but not sufficient for business permissions; admin access should also be network-restricted |
| No load/concurrency test of throttle | Transactional locking is implemented; run a concurrency test before high-traffic deployment |
| Local PostgreSQL credentials | Stored only in gitignored `backend/.env`; verified against PostgreSQL 14.18 on `127.0.0.1:5432` |

## Secure deployment checklist

- [ ] Generate a unique 50+ character `DJANGO_SECRET_KEY`, store it outside Git
      and outside OneDrive-synced plaintext if possible.
- [ ] Generate a separate 50+ character `JWT_SIGNING_KEY`; never reuse
      `DJANGO_SECRET_KEY` and never commit either value.
- [ ] Keep JWT token lifetimes short; the absolute session limit is a hard cap.
- [ ] Use a dedicated PostgreSQL role/database; not a superuser; TLS required.
- [ ] Set explicit `DJANGO_ALLOWED_HOSTS` and exact HTTPS
      `CSRF_TRUSTED_ORIGINS`.
- [ ] Set a non-default `ADMIN_URL` and, where possible, `ADMIN_ALLOWED_IPS`.
- [ ] Keep `ENABLE_API_DOCS=false` in production unless staff/network-restricted
      access is explicitly required.
- [ ] Terminate TLS at a controlled proxy; enable `TRUST_PROXY_HEADERS` only if
      the proxy overwrites forwarded headers.
- [ ] Add a restrictive CSP at the proxy/frontend layer.
- [ ] Run `python manage.py check --deploy` with production settings.
- [ ] Schedule `prune_login_throttles` and `prune_jwt_tokens`.
- [ ] Back up PostgreSQL and test restore; never commit `.env` or database
      dumps.
- [ ] Run `pip-audit`, tests, migrations drift check and schema validation in
      CI before release.
