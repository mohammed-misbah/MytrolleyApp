# Requirements Traceability — Milestone 1

Status values: **Verified** = implemented and covered by automated tests or a
recorded check; **Deferred** = intentionally outside milestone 1.

| ID | Requirement | Implementation | Verification | Status |
|---|---|---|---|---|
| R-01 | Python/Django/DRF/PostgreSQL only; no Docker, SQLite, Redis, YAML app config or microservices | `backend/requirements/`, `config/settings/base.py`, `DATABASES` uses `django.db.backends.postgresql`; no cache/Redis package | `pytest` creates a PostgreSQL test DB; `tests/test_health.py::test_readiness_executes_database_query` | Verified |
| R-02 | Inspect existing workspace; preserve prior work; isolate deliverable | Existing Node app remains in `Default Project`; project now lives at `Documents\MyTrolleyApp`; `frontend/` reserved and empty | Manual inspection; no files from the Node app were moved or edited | Verified |
| R-03 | Required layout: project/apps/tests/migrations in `backend/`, docs in `docs/`, README/.gitignore at root | Directory structure; `backend/manage.py`, `backend/accounts/migrations/0001_initial.py`, `docs/`, `README.md`, `.gitignore` | `manage.py makemigrations --check --dry-run` → “No changes detected” | Verified |
| R-04 | `.env` private; `.env.example` placeholders only | `backend/.env` is gitignored; `backend/.env.example` has placeholder values and comments | `.gitignore`; manual review of `.env.example` | Verified |
| R-05 | Custom user created before first migration | `accounts/models.py::User`; `AUTH_USER_MODEL`; migration `0001_initial.py` | `tests/test_commands.py::test_no_default_account_is_created_by_migrations`; migration applied on PostgreSQL | Verified |
| R-06 | Auth endpoints: login (issues access token and CSRF cookie), hidden refresh, single logout, current user | `accounts/urls.py`, `accounts/views.py` | `tests/test_auth.py`, `tests/test_jwt_security.py` (all auth flows) | Verified |
| R-07 | CSRF protection for cookie-authorized state changes; preserve admin CSRF | CSRF enforcement on cookie refresh; JSON-only login; Bearer logout; admin session/CSRF untouched | `test_cookie_refresh_without_csrf_is_rejected`, `test_refresh_cookie_can_be_used_with_csrf`, `test_body_refresh_does_not_require_csrf` | Verified |
| R-08 | JWT access/refresh issuance, rotation, reuse detection, absolute expiry and revocation | `accounts/tokens.py`, `accounts/authentication.py`, `AuthSession`; logout/Password-change/deactivation signals | Refresh-after-expiry, rotation, replay/family revocation, concurrency, absolute-expiry and logout tests | Verified |
| R-09 | Generic login failures; inactive users denied; no registration/default account | `InvalidCredentials`; inactive check; no register URL; interactive provisioning only | `test_login_failures_are_generic_for_wrong_unknown_and_inactive`, `test_no_public_registration_endpoint`, `test_no_default_account_is_created_by_migrations` | Verified |
| R-10 | Roles: Administrator, DataEntry; ungrouped authenticated denied; groups/permissions | `accounts/roles.py`, `accounts/permissions.py` | `test_roles_are_idempotent_and_exact`, `test_manage_users_permission_matrix`, `test_authenticated_user_without_group_has_no_business_permissions` | Verified |
| R-11 | Prevent role escalation | `StrictSerializer` rejects unknown fields; read-only `/me/`; safe response fields; staff alone does not grant business permissions | `test_unexpected_fields_are_rejected_not_ignored`, `test_me_requires_authentication_and_rejects_writes`, `test_permissions_are_reported_read_only`, `test_manage_users_permission_matrix` | Verified |
| R-12 | Default DRF permissions deny anonymous; public exceptions individual | `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`; explicit `AllowAny` on CSRF, login, health | `test_manage_users_permission_matrix`; health tests; auth tests | Verified |
| R-13 | DB-backed cross-process login abuse protection with cooldown/recovery | `accounts/throttling.py`, `LoginThrottle`, HMAC keys, transactional locking | `tests/test_throttling.py` including shared second client, case-insensitivity, window reset, success clears | Verified |
| R-14 | Production settings validation, fail closed | `config/settings/production.py`, `config/validation.py`, `config/env.py` | `tests/test_config.py`; `manage.py check --deploy` with production env → no issues | Verified |
| R-15 | Security headers, explicit hosts, no wildcard CORS | HSTS/SSL/cookies/nosniff/frame/referrer/COOP; `get_origins` rejects wildcards; no CORS package | Production settings and `test_config.py::test_origin_validation`; `check --deploy` | Verified |
| R-16 | Protect documentation and admin | Staff-only schema/docs in production; `API_DOCS_PUBLIC` development anonymous mode; staff-only admin; configurable admin path; optional IP allowlist; production docs disabled by default | `tests/test_security_surfaces.py` (permission modes, staff-only access, custom Swagger script); browser verification of anonymous docs; `test_config.py::test_admin_path_normalization_and_validation`, `test_network_allowlist_validation` | Verified |
| R-17 | Request size limits | `BoundedJSONParser`; `DATA_UPLOAD_*`; max JSON bytes | `tests/test_parsers.py`; `test_oversized_body_returns_413`, `test_oversized_string_is_rejected` | Verified |
| R-18 | Central error envelope with code/message/fields/request_id; consistent 401/403; no leaks | `core/errors.py`, `core/exception_handler.py`, `config/views.py`, request ID middleware | `tests/test_errors.py`, `tests/test_exception_mapping.py`, `tests/test_security_utils.py` | Verified |
| R-19 | Health `/live/` no DB and `/ready/` bounded query with generic 503 | `core/health.py`, `core/views.py`, `core/urls.py` | `tests/test_health.py` (query count, failure, no-store, no details) | Verified |
| R-20 | Ruff + type checking | `pyproject.toml`; Ruff E/F/W/I/B/UP/S/SIM/DJ; mypy with Django plugin | Auth slice: Ruff and format clean; `mypy accounts core config` no issues. Repo-wide run blocked by Milestone 2 `catalog` WIP | Verified (auth slice) |
| R-21 | pytest/pytest-django/coverage against PostgreSQL; minimum 85%; critical auth/authz tests | `backend/tests/`, coverage config, PostgreSQL test settings | 157 passed; 94.52% total coverage; isolated PostgreSQL 14.18 test DB | Verified |
| R-22 | drf-spectacular OpenAPI docs and validation; Swagger must exercise login/me/logout and keep refresh visible only in developer docs | `SPECTACULAR_SETTINGS`, `docs_permission_classes()`, custom `core/templates/core/swagger_ui.js`, `extend_schema`, refresh `exclude=True` | `spectacular --validate` exit 0; refresh absent from schema; browser flow login 200, Authorize, me 200, logout 200 with exact message, me 401 `SESSION_REVOKED` | Verified |
| R-23 | CI with PostgreSQL, migration drift, lint/type, coverage, dependency audit | `.github/workflows/ci.yml` (now includes a CI-only `JWT_SIGNING_KEY`) | Local auth-slice gates passed; the working tree is uncommitted so no CI run exists for it, and the repo-wide steps would still fail on Milestone 2 `catalog` WIP | Blocked |
| R-24 | Document future product/image/catalog/store design, ERD, trust boundaries, role matrix, milestone plan | `docs/architecture.md`, `docs/security.md`, `docs/api.md`, `docs/frontend-integration.md` | Manual review | Verified |
| R-25 | Run checks where possible, state blockers, provide exact PowerShell | `docs/verification.md`; commands in README | Live HTTP smoke, local PostgreSQL verification, Swagger browser flow and catalog blockers documented | Verified |
| R-26 | Do not implement React/Swift/product CRUD/images/deployment | `frontend/` empty; no product routers/models | Directory inspection; only auth/health routes exist | Deferred by scope |
| R-27 | Future milestones: catalog, images, stores, shopping list, clients | Design direction and rules in `docs/architecture.md` | Manual review | Deferred by scope |

## Evidence commands

```powershell
cd C:\Users\user\OneDrive\Documents\MyTrolleyApp\backend
.\.venv\Scripts\Activate.ps1

python -m ruff check accounts core config tests\test_auth.py tests\test_jwt_security.py tests\test_swagger_docs.py tests\test_errors.py tests\test_throttling.py tests\test_permissions.py tests\test_security_surfaces.py tests\test_commands.py tests\conftest.py
python -m ruff format --check accounts core config tests\test_auth.py tests\test_jwt_security.py tests\test_swagger_docs.py tests\test_errors.py tests\test_throttling.py tests\test_permissions.py tests\test_security_surfaces.py tests\test_commands.py tests\conftest.py
python -m mypy accounts core config
python -m pytest --cov --cov-report=term-missing --ignore=tests/test_catalog_api.py --ignore=tests/test_catalog_models.py
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --file openapi.yaml
python -m pip_audit -r requirements\production.txt
python -m pip_audit -r requirements\development.txt
```

Production deploy check (values are examples; use real ones):

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
$env:DJANGO_SECRET_KEY = "<unique 50+ character value>"
$env:JWT_SIGNING_KEY = "<different unique 50+ character value>"
$env:DJANGO_ALLOWED_HOSTS = "api.example.test"
$env:CSRF_TRUSTED_ORIGINS = "https://app.example.test"
$env:SECURE_HSTS_SECONDS = "31536000"
$env:SECURE_HSTS_INCLUDE_SUBDOMAINS = "true"
$env:SECURE_HSTS_PRELOAD = "true"
$env:DB_NAME = "mytrolley"
$env:DB_USER = "mytrolley_app"
$env:DB_PASSWORD = "<database password>"
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "5432"
$env:DB_SSLMODE = "require"
$env:ADMIN_URL = "ops-admin/"
python manage.py check --deploy
```
