# JWT Authentication Migration Record

Date started: 2026-11-17  
Status: **implemented and locally verified** (18 November 2026). The normative
contract is [api.md](api.md); this file records the migration decisions and what
shipped.

## Scope

Replace session/CSRF API authentication with a JWT Bearer lifecycle while
preserving users, password hashes, Django groups, the `Administrator` and
`DataEntry` roles, existing permissions, admin access, operational endpoints and
the existing architecture.

## Baseline findings

- DRF defaulted to `rest_framework.authentication.SessionAuthentication`.
- `POST /api/v1/auth/login/` called Django `login()` and rotated the session.
- `GET /api/v1/auth/csrf/` bootstrapped the CSRF cookie; login/logout required
  `X-CSRFToken`; the Swagger script injected it. (The bootstrap route and
  script were removed after the CSRF audit; login now sets the cookie.)
- `GET /api/v1/auth/me/` relied on the session cookie.
- Login abuse protection was PostgreSQL-backed (`LoginThrottle`).
- Django admin and staff documentation used sessions and CSRF.
- No JWT package, no auth-session table and no refresh endpoint existed.

## Decisions as shipped

1. **Library:** `djangorestframework-simplejwt` (pinned). No second auth stack.
2. **Algorithm:** HS256 for this single-backend deployment. Asymmetric signing
   is only justified when independent services must verify tokens.
3. **Secrets:** dedicated `JWT_SIGNING_KEY`, required at startup, at least 50
   characters, high variation, rejected if equal to `DJANGO_SECRET_KEY`.
4. **Access token:** 5 minutes, `Authorization: Bearer`, issuer, audience and
   token type checked, and the `sid` session checked on every request.
5. **Refresh token:** 1 day, `HttpOnly` cookie only, never in JSON, rotated on
   every use. There is **no** token-blacklist app; consumption is tracked by the
   session's current `refresh_jti`.
6. **Absolute session:** `AuthSession.expires_at` is fixed at login + 7 days and
   is never extended by rotation; a rotated refresh lifetime is capped at it.
7. **Session checks:** `SessionAwareJWTAuthentication` resolves the `sid` claim
   and rejects revoked, expired or inactive-user sessions immediately, so logout
   does not wait for access-token expiry.
8. **Reuse detection:** a refresh token whose `jti` is not the session's current
   `jti` is treated as consumed and revokes exactly its own token family. Other
   logins for the same user stay valid.
9. **Concurrency:** rotation locks the session row with `select_for_update()`.
   Exactly one concurrent request consumes a refresh token; duplicates trigger
   reuse handling. Clients must single-flight refresh.
10. **CSRF:** enforced when refresh authority comes from the cookie. JSON-body
    refresh tokens are explicit credentials and need no CSRF. Login is a
    JSON-only credential exchange, logout uses a non-ambient Bearer header, and
    Django admin keeps session authentication and CSRF.
11. **Documentation:** drf-spectacular Bearer support with its stock Swagger
    template. Login issues the readable `csrftoken` cookie; there is no public
    CSRF bootstrap route. `/api/v1/auth/refresh/` is excluded from the schema
    and Swagger UI but stays callable.
12. **Rate limiting:** existing PostgreSQL login throttle plus a PostgreSQL
    refresh throttle.
13. **Revocation:** logout (all caller sessions), password change, deactivation
    and reuse detection. New tokens are denied; existing access tokens fail on
    the next request because their session is no longer active.
14. **Browser storage:** no frontend exists yet. Documentation mandates
    memory-only access tokens and a single-flight refresh helper
    ([frontend-integration.md](frontend-integration.md)). No token is written to
    `localStorage`, `sessionStorage`, URLs or script-readable cookies.
15. **Key rotation:** documented as a maintenance-window procedure. A multi-key
    verification ring is acknowledged as future work, not claimed as present.

## Migrations

`accounts/migrations/0002`–`0008` add `AuthSession` and `RefreshThrottle` to the
existing schema. They were produced iteratively while the design changed, so the
chain contains add/remove/add steps for one column. It applies cleanly to a
fresh PostgreSQL database (proven by the test database created on every pytest
run) and `makemigrations --check` reports no drift. Squashing them before the
first production deploy is optional cleanup, not a correctness requirement.

## Rollback

- Restore the previous commit and redeploy. The new tables are additive; no
  user, group or permission rows are modified.
- Sessions in `django_sessions` are untouched by these migrations. Whether a
  pre-JWT session still authenticates after a rollback depends on its own expiry.
- Take a PostgreSQL backup before the production migration.

## Explicit non-goals / limitations

- No public registration, MFA, password-reset UI or iOS application.
- No frontend implementation; only the documented browser contract.
- No ZAP scan (no authorized target and tooling available).
- No claim of complete security; residual risks are listed in
  [security.md](security.md), and the executed checks in
  [verification.md](verification.md).
