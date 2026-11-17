# Security — Milestone 1

## Security objectives

Milestone 1 protects account credentials, sessions, role assignments and the
operational surface of the API. The design prioritises:

1. **No default access:** no default account, no public registration and
   default-deny API permissions.
2. **Revocable browser authentication:** database-backed sessions with CSRF
   protection and server-side invalidation.
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
| Session identifiers | Authenticated access without a password |
| CSRF tokens | Protection against cross-site state changes |
| Role/group/permission assignments | Business authorization and escalation |
| Database credentials and `DJANGO_SECRET_KEY` | Full data/system compromise |
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
- **Session storage.** `django.contrib.sessions.backends.db` stores sessions in
  PostgreSQL, shared by all application processes.
- **Cookie flags.** `sessionid` is `HttpOnly`, `SameSite=Lax`, `Secure` in
  production, with an 8-hour sliding expiry (`SESSION_SAVE_EVERY_REQUEST=True`).
- **Rotation.** Django's `login()` rotates the session key and deletes the old
  session row. The CSRF token is also rotated on login and logout.
- **Logout.** `POST /api/v1/auth/logout/` flushes the server-side session and
  returns `204`. A subsequent `/me/` request returns `401`.
- **Inactive users.** Django's authentication backend rejects inactive users,
  so they cannot log in; an existing session for a user later marked inactive
  is rejected by the authentication middleware.
- **Generic failures.** Wrong password, unknown user and inactive user all
  return the same `401 INVALID_CREDENTIALS` message. The response never reveals
  whether the account exists.
- **No JWT.** No bearer token is issued or stored in `localStorage`, avoiding a
  common browser token-exfiltration path and enabling immediate revocation.

## CSRF design

DRF's `SessionAuthentication` enforces CSRF only once a request is
authenticated. An anonymous login POST therefore needs explicit protection.

- `LoginView.post` is wrapped with Django's `csrf_protect`.
- `GET /api/v1/auth/csrf/` uses `ensure_csrf_cookie`, returns the masked token
  and sets the `csrftoken` cookie.
- `CSRF_COOKIE_HTTPONLY=False` because the browser must send the value in
  `X-CSRFToken`. The cookie is not an authentication secret by itself; the
  session cookie remains `HttpOnly`.
- `CSRF_COOKIE_SAMESITE="Lax"`, `CSRF_USE_SESSIONS=False`,
  `CSRF_COOKIE_AGE=28800`.
- `CSRF_TRUSTED_ORIGINS` accepts only exact `scheme://host[:port]` origins; the
  parser rejects wildcards, credentials, paths, queries and fragments.
- A CSRF failure on `/api/` returns the JSON envelope with `CSRF_FAILED`; the
  admin keeps Django's HTML 403 page.
- There is no CORS package. A same-origin deployment keeps the session/CSRF
  model simple and avoids cross-origin credential exposure.

## Authorization model

`REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]` is
`IsAuthenticated`. Public endpoints opt out individually:

- `GET /api/v1/auth/csrf/`
- `POST /api/v1/auth/login/` (still CSRF-protected)
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
  keys unreachable. Prune the table after a key rotation; existing sessions also
  become invalid because Django signs session data with the secret.

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
- Login successes/failures and CSRF failures are logged as events without the
  submitted password or username.
- Readiness failures log only the exception class, never the driver message.

## Production configuration and secrets

`config.settings.production` validates configuration at startup and fails
closed with variable names only:

- `DEBUG` false.
- `DJANGO_SECRET_KEY` at least 50 characters, not a known placeholder, with
  sufficient variation.
- Explicit `DJANGO_ALLOWED_HOSTS`; `*` is rejected.
- `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` true.
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
- The project Swagger script reads the current `csrftoken` cookie for every
  unsafe request, so login/logout rotation does not leave a stale token in the
  page.
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
| Session theft via compromised browser | Secure/HttpOnly/SameSite cookies, rotation, 8-hour expiry, server-side logout |
| Distributed password spraying | Per-username and per-IP DB limits reduce but do not eliminate |
| Throttle table growth | `prune_login_throttles` command; schedule it operationally |
| Secret rotation breaks sessions/throttle keys | Expected; rotate during a maintenance window and prune throttle rows |
| OneDrive-synced workspace | `backend/.env` is gitignored but may still sync to cloud storage; keep production secrets out of synced local files |
| Public development docs | Development defaults to anonymous docs so a fresh login can be tested; bind the dev server to localhost and set `API_DOCS_PUBLIC=false` if that exposure is unwanted |
| No malware scanning for future images | Explicitly deferred to milestone 3; design requires validation, re-encoding and scanning |
| Admin depends on staff flag | Staff is necessary but not sufficient for business permissions; admin access should also be network-restricted |
| No load/concurrency test of throttle | Transactional locking is implemented; run a concurrency test before high-traffic deployment |
| Local PostgreSQL credentials | Stored only in gitignored `backend/.env`; verified against PostgreSQL 14.18 on `127.0.0.1:5432` |

## Secure deployment checklist

- [ ] Generate a unique 50+ character `DJANGO_SECRET_KEY`, store it outside Git
      and outside OneDrive-synced plaintext if possible.
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
- [ ] Schedule `prune_login_throttles`.
- [ ] Back up PostgreSQL and test restore; never commit `.env` or database
      dumps.
- [ ] Run `pip-audit`, tests, migrations drift check and schema validation in
      CI before release.
