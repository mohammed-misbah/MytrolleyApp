# Verification — Milestone 1

Date of local verification: **17 November 2026**  
Project location: `C:\Users\user\OneDrive\Documents\MyTrolleyApp\`  
Platform: Windows, PowerShell, Python **3.14.8**

This document records what was actually run and observed. It does not claim a
successful check that was not executed.

## Verification environment

| Item | Value |
|---|---|
| Python | 3.14.8 |
| Virtual environment | `backend\.venv` (recreated after moving the project) |
| Django | 5.2.19 LTS |
| Django REST Framework | 3.18.3 |
| drf-spectacular | 0.30.0 |
| psycopg | 3.3.9 |
| PostgreSQL | 14.18 |
| Test database | `test_mytrolley` on the local PostgreSQL 14.18 service |
| Settings | `config.settings.test` for pytest; `config.settings.production` for deploy checks |
| CI | GitHub Actions `backend` workflow, run `44123969812` |

### Database used

Verification ran against the local PostgreSQL 14.18 service on
`127.0.0.1:5432`, using the role, database and password configured in the
gitignored `backend\.env`. Migrations were applied and `seed_roles` was run
against that database.

An earlier pass used a temporary PostgreSQL cluster because the local
credentials were not yet available. That cluster was stopped and removed. The
local service is now the verified database and is not part of the repository.

## Automated results

Command run from `C:\Users\user\OneDrive\Documents\MyTrolleyApp\backend`, with
the `.venv` interpreter and `backend\.env` loaded:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy .
python -m pytest --cov --cov-report=term-missing
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --file openapi.yaml
python -m pip_audit -r requirements\production.txt
python -m pip_audit -r requirements\development.txt
```

| Check | Result |
|---|---|
| `ruff check .` | **Passed** — all checks passed |
| `ruff format --check .` | **Passed** — 58 files already formatted |
| `mypy .` | **Passed** — no issues in 45 source files |
| `pytest --cov` | **112 passed**, **94.44%** total coverage (gate: 85%) |
| `makemigrations --check --dry-run` | **Passed** — “No changes detected” |
| `spectacular --validate` | **Passed** — 0 errors, 0 warnings |
| `pip_audit` production | **Passed** — no known vulnerabilities (exit 0) |
| `pip_audit` development | **Passed** — no known vulnerabilities after updating pytest to 9.0.3 |

Coverage was measured with branch coverage enabled. The lowest-covered
handwritten modules were the interactive admin command (79%, largely prompt
branches), config error branches (83%) and throttle recovery edges (88%); the
overall total remains well above the 85% gate.

### Production deploy check

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
$env:DJANGO_SECRET_KEY = "<50+ char verification key>"
$env:DJANGO_ALLOWED_HOSTS = "api.example.test"
$env:CSRF_TRUSTED_ORIGINS = "https://app.example.test"
$env:SECURE_HSTS_SECONDS = "31536000"
$env:SECURE_HSTS_INCLUDE_SUBDOMAINS = "true"
$env:SECURE_HSTS_PRELOAD = "true"
$env:DB_NAME = "mytrolley"
$env:DB_USER = "mytrolley_verifier"
$env:DB_PASSWORD = "<verification-only password>"
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "55434"
$env:DB_SSLMODE = "require"
$env:ADMIN_URL = "ops-admin/"
python manage.py check --deploy
```

Observed result:

```text
System check identified no issues (0 silenced).
```

The earlier drf-spectacular warning on `LogoutView` was fixed by declaring
`request=None` in its schema extension.

## CI result

The repository was pushed to
`https://github.com/mohammed-misbah/MytrolleyApp` and the `backend` workflow
completed successfully for the milestone commit:

- Run: `https://github.com/mohammed-misbah/MytrolleyApp/actions/runs/44123969812`
- Commit: `19d9b55aa3aa0de53df72ae38ee3d94bf3fc0e12`
- Result: **success**

All steps passed: Ruff lint, Ruff format check, mypy, migration drift,
OpenAPI validation, production deploy check, PostgreSQL tests with coverage,
both dependency audits, and coverage artifact upload.

## Live HTTP smoke test

A real Django development server was started on `127.0.0.1:8011` against the
local PostgreSQL database. A temporary Administrator user was created for the
smoke test and deleted afterwards. The server was stopped after the test.

Observed response values:

```json
{
  "live": "ok",
  "ready": "ready",
  "login_user": "smoke_admin",
  "roles": "Administrator",
  "me_user": "smoke_admin",
  "logout_status": 204,
  "me_after_logout": 401
}
```

This confirms:

- `/api/v1/health/live/` returns `{"status": "ok"}`
- `/api/v1/health/ready/` returns `{"status": "ready"}`
- CSRF bootstrap + login succeeds with a real cookie jar and `X-CSRFToken`
- `/api/v1/auth/me/` returns the authenticated user
- Logout returns `204`
- `/api/v1/auth/me/` afterwards returns `401`

A first logout attempt produced a Windows PowerShell 5.1 `Invoke-WebRequest`
non-interactive/IE-parsing error even though the session was invalidated. The
test was repeated with `-UseBasicParsing`; the recorded result above is from
that clean run.

## Swagger UI browser verification

Date: **17 November 2026**. Tool: the in-app browser.

Environment: development settings (`config.settings.development`),
`ENABLE_API_DOCS=true`, `API_DOCS_PUBLIC=true`, local PostgreSQL, and a
dedicated server on `http://127.0.0.1:8021/` with a clean cookie jar. The normal
development URL is `http://127.0.0.1:8000/api/v1/docs/`; port 8021 was used to
avoid cookies from an existing server.

A single-use staff user was created for the test and deleted afterwards. No
password, session cookie, or CSRF token values are recorded here.

Steps performed in the page:

1. Opened `/api/v1/docs/` anonymously.
2. Expanded **Authentication**.
3. Executed `GET /api/v1/auth/csrf/`.
4. Executed `POST /api/v1/auth/login/` with the temporary credentials.
5. Executed `GET /api/v1/auth/me/`.
6. Executed `POST /api/v1/auth/logout/`.
7. Executed `GET /api/v1/auth/me/` again.

Observed:

| Step | Observed |
|---|---|
| Anonymous docs page | `200`; 6 operations rendered |
| CSRF bootstrap | `200`; `csrftoken` cookie set |
| Login | `200`; user returned with `Administrator`; exactly one `X-CSRFToken` header (32 chars); cookies preserved |
| Current user | `200`; same user |
| Logout | `204`; cookies preserved |
| Current user after logout | `401 UNAUTHENTICATED` |

CSRF rotation was checked with SHA-256 hashes rather than token values: the
hashes before login, after login, and after logout were all different. The
required `X-CSRFToken` field in Swagger was filled automatically from the
current cookie after each rotation, and the request interceptor replaced it on
every unsafe request. The session cookie is `HttpOnly`, so it is correctly not
visible to JavaScript.

Two problems were found and fixed during this verification:

1. The stock drf-spectacular script embedded the token at page-render time, so
   it went stale after login/logout rotation. The project script now reads the
   current cookie for every unsafe request.
2. Sending the Swagger parameter and the interceptor header under different
   casing produced one combined invalid value and `403 CSRF_FAILED`. The
   interceptor now replaces the existing case-insensitive header key.

The full flow was repeated after the fixes and passed.

## Test coverage map

| Area | Test file | Representative checks |
|---|---|---|
| Auth/session/CSRF | `tests/test_auth.py` | CSRF bootstrap, rotation, generic failures, logout, inactive sessions, no registration |
| Error envelope | `tests/test_errors.py` | 404/405, malformed JSON, unknown fields, 413/415, request IDs, no sensitive values, 500 handling |
| Exception mapping | `tests/test_exception_mapping.py` | Every DRF/Django exception branch, retry headers, validation flattening |
| Permissions/roles | `tests/test_permissions.py` | Exact idempotent roles, Administrator/DataEntry/ungrouped/staff matrix |
| Login throttling | `tests/test_throttling.py` | Username/IP limits, shared DB state, case folding, cooldown, success recovery, window reset |
| Health | `tests/test_health.py` | Live query count 0, readiness query, generic 503, no driver details |
| Config/security | `tests/test_config.py` | Env parsing, origins, admin path, IP networks, secret handling, production validation |
| Commands | `tests/test_commands.py` | Role seeding, no default account, interactive admin, weak/mismatched passwords, pruning |
| Security surfaces | `tests/test_security_surfaces.py` | Admin/docs permission modes, custom Swagger CSRF script, admin IP allowlist, log redaction, password not logged |
| Security utilities | `tests/test_security_utils.py` | Proxy IP trust, malformed forwarded headers, Django JSON handlers, non-API CSRF HTML |
| Parser boundaries | `tests/test_parsers.py` | Content-Length bounds, oversized body, empty/non-UTF-8/malformed JSON |

## What was not verified locally

These are honest limitations, not passed checks:

1. **React frontend end-to-end flow.** Milestone 1 deliberately has no
   frontend. The Swagger UI browser flow is verified separately above.
2. **Load, concurrency or soak testing.** Throttle locking is transactional, but
   no high-concurrency stress test was run.
3. **Production infrastructure.** No TLS proxy, HSTS deployment, CSP, database
   TLS certificate, backup/restore or monitoring was provisioned.
4. **Image upload security.** Deferred to a later milestone.
5. **Swift client.** Deferred.

## Reproduce the checks

The same commands can be reproduced from
`C:\Users\user\OneDrive\Documents\MyTrolleyApp\backend`:

```powershell
.\.venv\Scripts\Activate.ps1

# backend\.env is already configured; copy the template only on a new machine.
Copy-Item .env.example .env
notepad .env
# Set DJANGO_SECRET_KEY (50+ random characters) and your real DB_* values.
```

Create the role/database (as a PostgreSQL administrator):

```sql
CREATE ROLE mytrolley_app LOGIN PASSWORD 'replace-with-a-local-password';
CREATE DATABASE mytrolley OWNER mytrolley_app;
-- pytest/Django needs to create test_mytrolley:
ALTER ROLE mytrolley_app CREATEDB;
```

Then:

```powershell
python manage.py migrate
python manage.py seed_roles
python manage.py create_initial_admin

python -m ruff check .
python -m ruff format --check .
python -m mypy .
python -m pytest --cov --cov-report=term-missing
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --file openapi.yaml
python -m pip_audit -r requirements\production.txt
```

If you cannot grant `CREATEDB`, create `test_mytrolley` manually and set
`TEST_DB_NAME` in `.env`; the test runner must be able to create/drop or reuse
that test database.

Live local check:

```powershell
python manage.py runserver
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live/
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready/
```

## Cleanup performed

- The temporary smoke-test user was deleted.
- The smoke-test development server was stopped.
- The generated OpenAPI file used for validation was removed
  (`openapi.yaml` is gitignored and reproducible).
- The earlier temporary PostgreSQL cluster was stopped and its data directory
  removed. The local PostgreSQL service and application database are retained.
- The reserved `frontend/` directory now contains `.gitkeep` so Git preserves it.
- The project's `.venv` was recreated after the move so its Windows paths point
  to the new location.
