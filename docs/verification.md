# Verification — Milestone 1 (JWT Authentication Slice)

Date of local verification: **18 November 2026**  
Project location: `C:\Users\user\OneDrive\Documents\MyTrolleyApp\`  
Platform: Windows, PowerShell, Python **3.14.8**

This document records what was actually run and observed. It does not claim a
successful check that was not executed. Passing tests reduce known risk; they do
not prove that the system is free of security defects.

## Verification environment

| Item | Value |
|---|---|
| Python | 3.14.8 |
| Virtual environment | `backend\.venv` |
| Django | 5.2.19 LTS |
| Django REST Framework | 3.18.3 |
| drf-spectacular | 0.30.0 |
| djangorestframework-simplejwt | installed with the JWT slice |
| psycopg | 3.3.9 |
| PostgreSQL | 14.18 |
| Test database | isolated `test_mytrolley` on the local PostgreSQL 14.18 service |
| Settings | `config.settings.test` for pytest; `config.settings.development` for the live server; `config.settings.production` for the deploy check |

### Database used

Verification ran against the local PostgreSQL 14.18 service on
`127.0.0.1:5432`, using the role, database and password configured in the
gitignored `backend\.env`. The test runner created and destroyed the isolated
`test_mytrolley` database. Development users and data were preserved; the only
live-server user was a temporary smoke-test account that was deleted afterwards.

## Automated results

Commands run from `C:\Users\user\OneDrive\Documents\MyTrolleyApp\backend` with
the `.venv` interpreter and `backend\.env` loaded.

The authentication slice is verified with the two Milestone 2 `catalog` test
modules excluded. Those modules are work in progress and cannot be collected
because `catalog` is not in `INSTALLED_APPS`; they are not authentication tests.

```powershell
python -m ruff check accounts core config tests\test_auth.py tests\test_jwt_security.py tests\test_swagger_docs.py tests\test_errors.py tests\test_throttling.py tests\test_permissions.py tests\test_security_surfaces.py tests\test_commands.py tests\conftest.py
python -m ruff format --check accounts core config tests\test_auth.py tests\test_jwt_security.py tests\test_swagger_docs.py tests\test_errors.py tests\test_throttling.py tests\test_permissions.py tests\test_security_surfaces.py tests\test_commands.py tests\conftest.py
python -m mypy accounts core config
python -m pytest --cov --cov-report=term-missing --ignore=tests/test_catalog_api.py --ignore=tests/test_catalog_models.py
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --file openapi.verify.yaml
python -m pip_audit -r requirements\production.txt
python -m pip_audit -r requirements\development.txt
```

| Check | Result | Evidence |
|---|---|---|
| `ruff check` (auth slice) | **Passed** | “All checks passed!” |
| `ruff format --check` (auth slice) | **Passed** | 57 files already formatted |
| `mypy accounts core config` | **Passed** | “Success: no issues found in 48 source files” |
| `pytest --cov` (auth slice) | **Passed** | **157 passed**, **94.52%** total coverage (gate 85%) |
| `manage.py check` | **Passed** | “System check identified no issues (0 silenced).” |
| `makemigrations --check --dry-run` | **Passed** | “No changes detected” (exit 0) |
| `spectacular --validate` | **Passed** | exit 0; `securitySchemes.jwtAuth` present |
| OpenAPI refresh exclusion | **Passed** | `/api/v1/auth/refresh/` absent from `paths` |
| Production `check --deploy` | **Passed** | no issues with production settings and `JWT_SIGNING_KEY` |
| `pip_audit` production | **Passed** | no known vulnerabilities (exit 0) |
| `pip_audit` development | **Passed** | no known vulnerabilities (exit 0) |

The previous baseline recorded in this document was 112 tests. The current
count is 157 because the JWT migration tests were added and because
`tests/test_errors.py` and `tests/test_throttling.py` now collect after their
stale session-era CSRF helper was removed. No test was skipped or weakened to
reach this count.

### Repo-wide quality-gate blockers (not authentication failures)

| Command | Result | Cause |
|---|---|---|
| `ruff check .` | **Blocked** | 96 lint errors in `catalog/*` and `tests/test_catalog_*` |
| `ruff format --check .` | **Blocked** | 7 Milestone 2 files under `catalog/` and `tests/test_catalog_*` would be reformatted |
| `mypy .` | **Blocked** | 66 errors in 3 catalog/WIP files |
| `pytest` (no ignores) | **Blocked** | collection fails in `tests/test_catalog_api.py` and `tests/test_catalog_models.py`: `catalog` is not in `INSTALLED_APPS` |

These are Milestone 2 work-in-progress files. Authentication-scope lint, types,
tests and schema validation pass. Fixing the catalog app would require starting
Milestone 2 and was not done.

## Live HTTP smoke test

A development server was started on `127.0.0.1:8031` against local PostgreSQL.
A temporary Administrator user was created for the test and deleted afterwards.
The server was stopped after the test. Passwords and token values are not
recorded here.

Observed results:

| Step | Observed |
|---|---|
| Login | `200`; `access` present; `refresh` absent from JSON |
| Refresh cookie | `HttpOnly`, `Path=/api/v1/auth/`, `SameSite=Lax` under development HTTP |
| `/me/` with access token | `200`; correct username and Administrator permissions |
| CSRF bootstrap | `200`; `csrftoken` cookie set |
| Cookie refresh with `X-CSRFToken` | `200`; new access token; refresh cookie rotated |
| `/me/` with refreshed access | `200` |
| Replay consumed refresh token | `401 INVALID_REFRESH_TOKEN` |
| Current refresh token after replay | `401 SESSION_REVOKED` (family revoked) |
| Logout | `200`; exact message `Logout successful. All active sessions for the current user have been revoked.` |
| Old access after logout | `401 SESSION_REVOKED` |
| Refresh after logout | `401 SESSION_REVOKED` |
| Fresh login after logout | `200` |
| Schema | refresh path absent; `jwtAuth` present |
| Swagger UI page | `200` |

## Swagger UI browser verification

Date: **18 November 2026**. Tool: the in-app browser.

Environment: development settings, `ENABLE_API_DOCS=true`,
`API_DOCS_PUBLIC=true`, local PostgreSQL, dedicated server on
`http://127.0.0.1:8031/`, and an anonymous docs page. A temporary test user was
used and deleted afterwards.

Steps performed in the page:

1. Opened `/api/v1/docs/` anonymously.
2. Expanded **Authentication** and executed `POST /api/v1/auth/login/` with the
   temporary credentials.
3. Clicked **Authorize**, pasted only the returned `access` token and confirmed
   `jwtAuth (http, Bearer)` became authorized.
4. Executed `GET /api/v1/auth/me/`.
5. Executed `POST /api/v1/auth/logout/`.
6. Executed `GET /api/v1/auth/me/` again.

Observed:

| Step | Observed |
|---|---|
| Login in Swagger | `200`; response contained `access`, `token_type`, `expires_in`, `refresh_expires_in` and `user`; no `refresh` property |
| Authorize dialog | `jwtAuth (http, Bearer)` reported **Authorized** after pasting the access token |
| Current user | `200`; correct user, roles and permissions |
| Logout | `200`; live response body exactly `{"message": "Logout successful. All active sessions for the current user have been revoked."}` |
| Current user after logout | `401 SESSION_REVOKED` with `WWW-Authenticate: Bearer` |
| Refresh operation | Absent from the rendered operation list and the schema |
| Browser storage | `localStorage` and `sessionStorage` contained no token entries |
| Cookie visibility | `document.cookie` contained `csrftoken` and did **not** contain `refresh_token` (HttpOnly) |
| Console | No JavaScript errors; one expected network error for the deliberate `401` after logout |

The browser flow proves that Bearer authorization sends the access token and
that logout revokes it immediately. It does not exercise the hidden refresh
endpoint through Swagger (by design); refresh was exercised in the live HTTP
smoke test above.

## Test coverage map

| Area | Test file | Representative checks |
|---|---|---|
| Authentication contract | `tests/test_auth.py` | Login shape, wrong credentials, inactive user, `/me/` validity, expiry, tampering, wrong algorithm/issuer/audience/type, refresh after expiry, rotation, reuse, absolute expiry, logout 200 message, both token types revoked, other-user isolation, fresh login, inactive/password-change revocation, cookie flags/clearing, CSRF on cookie refresh, fail-closed login/refresh/logout, no registration |
| JWT attack surface | `tests/test_jwt_security.py` | Concurrent logins, concurrent refresh, concurrent logout, reuse revoking one family, legacy tokens, refresh throttling, token-size abuse |
| Swagger/schema | `tests/test_swagger_docs.py` | Docs render, CSRF bootstrap, refresh hidden, login schema has no `refresh` |
| Error envelope | `tests/test_errors.py` | 404/405, malformed JSON, unknown fields, 413/415, request IDs, no sensitive values, 500 handling |
| Exception mapping | `tests/test_exception_mapping.py` | Every DRF/Django exception branch, retry headers, validation flattening |
| Permissions/roles | `tests/test_permissions.py` | Exact idempotent roles, Administrator/DataEntry/ungrouped/staff matrix |
| Login throttling | `tests/test_throttling.py` | Username/IP limits, shared DB state, case folding, cooldown, success recovery, window reset |
| Commands | `tests/test_commands.py` | Role seeding, no default account, interactive admin, throttle and JWT/session pruning |
| Health | `tests/test_health.py` | Live query count 0, readiness query, generic 503, no driver details |
| Config/security | `tests/test_config.py` | Env parsing, origins, admin path, IP networks, secret handling, production validation |
| Security surfaces | `tests/test_security_surfaces.py` | Admin/docs permission modes, custom Swagger CSRF script, admin IP allowlist, log redaction, password not logged |
| Security utilities | `tests/test_security_utils.py` | Proxy IP trust, malformed forwarded headers, Django JSON handlers, non-API CSRF HTML |
| Parser boundaries | `tests/test_parsers.py` | Content-Length bounds, oversized body, empty/non-UTF-8/malformed JSON |

## What was not verified locally

These are honest limitations, not passed checks:

1. **React or iOS client end-to-end flow.** No frontend or app was built in this
   milestone. The browser flow used Swagger UI and a raw HTTP client only.
2. **Runtime refresh through Swagger UI.** Refresh is intentionally hidden from
   the page; it was tested through the live HTTP client instead.
3. **Load, concurrency or soak testing at scale.** Concurrency tests use two
   threads against PostgreSQL, not a production traffic profile.
4. **Production infrastructure.** No TLS proxy, HSTS deployment, CSP, database
   TLS certificate, backup/restore or monitoring was provisioned.
5. **CI for this working tree.** The changes are uncommitted and were not
   pushed; the earlier CI run in project history predates the JWT slice.
6. **Image upload security and product features.** Deferred to later
   milestones.
7. **Security proof.** The suite checks documented behavior under specific
   attacks. It cannot prove the absence of all vulnerabilities; review,
   dependency updates and operational controls remain necessary.

## Reproduce the checks

```powershell
cd C:\Users\user\OneDrive\Documents\MyTrolleyApp\backend
.\.venv\Scripts\Activate.ps1

# Required secrets: generate distinct random values of 50+ characters.
# backend\.env must define DJANGO_SECRET_KEY and JWT_SIGNING_KEY.
python manage.py migrate
python manage.py seed_roles
python manage.py create_initial_admin

python -m ruff check accounts core config tests\test_auth.py tests\test_jwt_security.py tests\test_swagger_docs.py tests\test_errors.py tests\test_throttling.py tests\test_permissions.py tests\test_security_surfaces.py tests\test_commands.py tests\conftest.py
python -m ruff format --check accounts core config tests\test_auth.py tests\test_jwt_security.py tests\test_swagger_docs.py tests\test_errors.py tests\test_throttling.py tests\test_permissions.py tests\test_security_surfaces.py tests\test_commands.py tests\conftest.py
python -m mypy accounts core config
python -m pytest --cov --cov-report=term-missing --ignore=tests/test_catalog_api.py --ignore=tests/test_catalog_models.py
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --file openapi.verify.yaml
```

The test runner must be able to create/drop or reuse the isolated test database.
Set `TEST_DB_NAME` if `CREATEDB` is unavailable.

Live local check:

```powershell
python manage.py runserver 127.0.0.1:8031
```

Then follow [api.md](api.md) for login, `/me/`, refresh through a cookie-aware
client, logout and old-token rejection.

## Cleanup performed

- The temporary smoke-test user and its sessions were deleted.
- The smoke-test development server was stopped.
- Temporary smoke-test scripts, logs and PID files were removed.
- The generated `openapi.verify.yaml` used for validation was removed.
- Development users and data were not deleted.
