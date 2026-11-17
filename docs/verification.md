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
| Test database | `test_mytrolley` on an isolated local cluster |
| Settings | `config.settings.test` for pytest; `config.settings.production` for deploy checks |

### Why an isolated PostgreSQL cluster was used

The pre-installed PostgreSQL 14 Windows service on `127.0.0.1:5432` required
credentials that were not available to the agent. Direct connection attempts
failed with password authentication errors. To avoid inventing results or
altering the user's existing database service, verification used a separate,
temporary PostgreSQL 14 cluster under:

```text
C:\Users\user\AppData\Local\Temp\opencode\mytrolley-pg
```

It listened on a non-default local port and used a verification-only role and
database. It is **not** part of the deliverable and must not be used as the
project's production database. The project itself defaults to
`127.0.0.1:5432`; you must supply your own local credentials in
`backend\.env`.

## Automated results

Command run from `C:\Users\user\OneDrive\Documents\MyTrolleyApp\backend`, with
the `.venv` interpreter and the test database environment variables set:

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
| `pytest --cov` | **111 passed**, **94.42%** total coverage (gate: 85%) |
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

## Live HTTP smoke test

A real Django development server was started on `127.0.0.1:8011` against the
verification database. A temporary Administrator user was created for the
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
| Security surfaces | `tests/test_security_surfaces.py` | Admin/docs staff-only, admin IP allowlist, log redaction, password not logged |
| Security utilities | `tests/test_security_utils.py` | Proxy IP trust, malformed forwarded headers, Django JSON handlers, non-API CSRF HTML |
| Parser boundaries | `tests/test_parsers.py` | Content-Length bounds, oversized body, empty/non-UTF-8/malformed JSON |

## What was not verified locally

These are honest limitations, not passed checks:

1. **The user's existing PostgreSQL 14 service.** Credentials were unavailable,
   so no migration or test ran against `127.0.0.1:5432` with the user's real
   role/database.
2. **GitHub Actions execution.** The workflow exists but was not pushed to a
   repository, so the remote CI run has not happened.
3. **Browser/React end-to-end flow.** Milestone 1 deliberately has no frontend.
4. **Load, concurrency or soak testing.** Throttle locking is transactional, but
   no high-concurrency stress test was run.
5. **Production infrastructure.** No TLS proxy, HSTS deployment, CSP, database
   TLS certificate, backup/restore or monitoring was provisioned.
6. **Image upload security.** Deferred to a later milestone.
7. **Swift client.** Deferred.

## Run the same checks on your own PostgreSQL

From `C:\Users\user\OneDrive\Documents\MyTrolleyApp\backend`:

```powershell
.\.venv\Scripts\Activate.ps1

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
- The verification PostgreSQL cluster was stopped and its temporary data
  directory removed after verification. It was separate from the project and
  contained no deliverable credentials or data.
- The project's `.venv` was recreated after the move so its Windows paths point
  to the new location.
