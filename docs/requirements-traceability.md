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
| R-06 | Auth endpoints: CSRF bootstrap, login, POST logout, current user | `accounts/urls.py`, `accounts/views.py` | `tests/test_auth.py` (all auth flows) | Verified |
| R-07 | Enforce CSRF on login explicitly | `LoginView.post` wrapped with `csrf_protect`; `CSRF_FAILURE_VIEW`; `csrf_failure` handler | `test_login_without_csrf_is_rejected`, `test_login_with_invalid_csrf_is_rejected`, `test_login_with_origin_mismatch_is_rejected` | Verified |
| R-08 | Rotate session on login; invalidate on logout | Django `login()`/`logout()`; explicit CSRF `rotate_token` | `test_valid_login_returns_safe_user_and_rotates_session`, `test_logout_invalidates_session_and_requires_csrf` | Verified |
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
| R-20 | Ruff + type checking | `pyproject.toml`; Ruff E/F/W/I/B/UP/S/SIM/DJ; mypy with Django plugin | `ruff check .` → clean; `ruff format --check .` → clean; `mypy .` → 45 files, no issues | Verified |
| R-21 | pytest/pytest-django/coverage against PostgreSQL; minimum 85%; critical auth/authz tests | `backend/tests/`, coverage config, PostgreSQL test settings | 112 passed; 94.44% total coverage; verified against local PostgreSQL 14.18 and in CI | Verified |
| R-22 | drf-spectacular OpenAPI docs and validation; Swagger must exercise the session/CSRF auth flow | `SPECTACULAR_SETTINGS`, `docs_permission_classes()`, custom `core/templates/core/swagger_ui.js`, `extend_schema` on endpoints | `manage.py spectacular --validate --file openapi.yaml` — errors 0, warnings 0; browser flow: CSRF 200, login 200, me 200, logout 204, me 401; CSRF rotation observed | Verified |
| R-23 | CI with PostgreSQL, migration drift, lint/type, coverage, dependency audit | `.github/workflows/ci.yml` | GitHub Actions run `44123969812` completed successfully; all workflow steps passed | Verified |
| R-24 | Document future product/image/catalog/store design, ERD, trust boundaries, role matrix, milestone plan | `docs/architecture.md`, `docs/security.md`, `docs/api.md` | Manual review | Verified |
| R-25 | Run checks where possible, state blockers, provide exact PowerShell | `docs/verification.md`; commands in README | Live HTTP smoke, local PostgreSQL verification, CI run and Swagger browser flow documented | Verified |
| R-26 | Do not implement React/Swift/product CRUD/images/deployment | `frontend/` empty; no product routers/models | Directory inspection; only auth/health routes exist | Deferred by scope |
| R-27 | Future milestones: catalog, images, stores, shopping list, clients | Design direction and rules in `docs/architecture.md` | Manual review | Deferred by scope |

## Evidence commands

```powershell
cd C:\Users\user\OneDrive\Documents\MyTrolleyApp\backend
.\.venv\Scripts\Activate.ps1

python -m ruff check .
python -m ruff format --check .
python -m mypy .
python -m pytest --cov --cov-report=term-missing
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --file openapi.yaml
python -m pip_audit -r requirements\production.txt
python -m pip_audit -r requirements\development.txt
```

Production deploy check (values are examples; use real ones):

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
$env:DJANGO_SECRET_KEY = "<unique 50+ character value>"
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
