# Requirements Traceability — MY Trolley

Status values: **Verified** = implemented and covered by automated tests or a
recorded check; **Verified locally** = every command in `.github/workflows/ci.yml`
was executed successfully in the local environment (no GitHub Actions run was
performed in this environment); **Pending** = intentionally deferred work
(Tests 26–29: cloud image storage, deployment/packaging, native iOS integration
and final UI/UX polish).

Manual verification of Tests 1–25 and FV.1–FV.7 was completed separately and is
not repeated here.

| ID | Requirement | Implementation | Verification | Status |
|---|---|---|---|---|
| R-01 | Python/Django/DRF/PostgreSQL only; no Docker, SQLite, Redis, YAML app config or microservices | `backend/requirements/`, `config/settings/base.py`, PostgreSQL backend | pytest creates an isolated PostgreSQL test DB; `tests/test_health.py` | Verified |
| R-02 | Inspect existing workspace; preserve prior work; isolate deliverable | Project isolated under `Documents/MyTrolleyApp`; prior Node app untouched | Manual inspection | Verified |
| R-03 | Required layout: project/apps/tests/migrations in `backend/`, docs in `docs/`, README/.gitignore at root | Directory structure; `backend/manage.py`; migrations; `docs/`; `.gitignore` | `manage.py makemigrations --check --dry-run` → “No changes detected” | Verified |
| R-04 | `.env` private; `.env.example` placeholders only | Only `.env.example` files are tracked; real `.env` files gitignored | `git ls-files` review | Verified |
| R-05 | Custom user created before first migration | `accounts/models.py::User`; `AUTH_USER_MODEL`; migration `0001_initial.py` | `tests/test_commands.py` | Verified |
| R-06 | Auth endpoints: login, hidden refresh, single logout, current user | `accounts/urls.py`, `accounts/views.py` | `tests/test_auth.py`, `tests/test_jwt_security.py` | Verified |
| R-07 | CSRF protection for cookie-authorized state changes; admin CSRF preserved | CSRF on cookie refresh only; JSON-only login; Bearer logout | `tests/test_auth.py` CSRF cases | Verified |
| R-08 | JWT access/refresh issuance, rotation, reuse detection, absolute expiry, revocation | `accounts/tokens.py`, `accounts/authentication.py`, `AuthSession` | Rotation, replay/family revocation, concurrency and expiry tests | Verified |
| R-09 | Generic login failures; inactive users denied; no registration/default account | `InvalidCredentials`; inactive check; no register URL | `tests/test_auth.py` | Verified |
| R-10 | Roles Administrator/DataEntry; ungrouped users denied; groups and permissions | `accounts/roles.py`, `accounts/permissions.py` | `tests/test_permissions.py` | Verified |
| R-11 | Prevent role escalation | Strict serializers reject unknown fields; read-only `/me/`; safe payloads | `tests/test_unexpected_fields.py`, `tests/test_security_surfaces.py` | Verified |
| R-12 | Default DRF permissions deny anonymous; explicit public exceptions | `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` | Auth and health tests | Verified |
| R-13 | DB-backed login abuse protection with cooldown/recovery | `accounts/throttling.py`, `LoginThrottle` | `tests/test_throttling.py` | Verified |
| R-14 | Production settings validation, fail closed | `config/settings/production.py`, `config/validation.py` | `tests/test_config.py`; `manage.py check --deploy` | Verified |
| R-15 | Security headers, explicit hosts, no wildcard CORS | Production settings and origin validation | `tests/test_config.py`; `check --deploy` | Verified |
| R-16 | Protect documentation and admin | Staff-only schema/docs in production; dev-only anonymous docs; configurable admin path | `tests/test_security_surfaces.py` | Verified |
| R-17 | Request size limits | `BoundedJSONParser`; `DATA_UPLOAD_*` | `tests/test_parsers.py`, `tests/test_errors.py` | Verified |
| R-18 | Central error envelope with code/message/fields/request_id | `core/errors.py`, `core/exception_handler.py`, request-ID middleware | `tests/test_errors.py`, `tests/test_exception_mapping.py` | Verified |
| R-19 | Health `/live/` no DB; `/ready/` bounded query with generic 503 | `core/health.py`, `core/views.py` | `tests/test_health.py` | Verified |
| R-20 | Ruff and mypy quality gates | `pyproject.toml` (E/F/W/I/B/UP/S/SIM/DJ; mypy with Django plugin) | Repo-wide `ruff check .`, `ruff format --check .` and `mypy .` all pass: 223 → 0 lint errors, 14 → 0 unformatted files, 8 → 0 type errors | Verified |
| R-21 | pytest/pytest-django/coverage on PostgreSQL; ≥85% | `backend/tests/`, coverage config | **319 passed, 0 failed**; coverage **94.10%**; unfiltered collection succeeds | Verified |
| R-22 | drf-spectacular OpenAPI docs and validation | `SPECTACULAR_SETTINGS`, custom Swagger UI, `extend_schema` | `manage.py spectacular --validate --file openapi.yaml` exit 0 | Verified |
| R-23 | CI with PostgreSQL, migration drift, lint/type, coverage, dependency audit | `.github/workflows/ci.yml` | Every configured step executed locally and passed, including unfiltered pytest, repo-wide Ruff/format/mypy, `check --deploy` and both pip-audit runs. No GitHub Actions run was performed in this environment | Verified locally |
| R-24 | Document product/image/catalog/store design, ERD, trust boundaries, role matrix | `docs/architecture.md`, `docs/security.md`, `docs/api.md`, `docs/database.md` | Manual review; ERD and product lifecycle updated for soft deletion | Verified |
| R-25 | Run checks where possible, state blockers, provide exact PowerShell | `docs/verification.md`; README | CI-equivalent commands documented and executed | Verified |
| R-26 | React web dashboard and product CRUD (formerly deferred by Milestone 1) | `frontend/` React/Vite/TS/Tailwind app; `catalog/` CRUD APIs | Frontend `typecheck` and production build pass; 319 backend tests cover catalog CRUD | Verified |
| R-27 | Images, stores, catalog and clients | Image upload metadata, store pricing/inventory, React client implemented; native iOS client not present | Catalog and frontend tests; no mobile code in repo | Pending (Test 28) |
| R-28 | Strict field validation on all catalog write serializers | `core/serializers.py::StrictModelSerializer`; six write serializers | `tests/test_unexpected_fields.py` (8 tests) | Verified |
| R-29 | Product soft deletion separate from deactivation | `deleted_at`, `ProductManager`/`all_objects`, migration `0005_product_soft_delete`, `DELETE /api/v1/products/{id}/` | `tests/test_product_deletion.py` (20 tests) | Verified |
| R-30 | Database query optimization and case-insensitive uniqueness | Single filter/sort/count block; prefetch-safe serializers; migration `0004` | `tests/test_query_optimization.py`, `tests/test_database_constraints.py` | Verified |
| R-31 | Independent store pricing and inventory, filtering/sorting/pagination | `ProductStore` associations; search serializer | `tests/test_catalog_api.py`, `tests/test_price_filter.py`, `tests/test_price_sorting.py` | Verified |
| R-32 | Manual live-server scripts must not expose credentials or break collection | `backend/tools/manual_jwt_*.py`; runtime env/prompt input only | Unfiltered pytest collects them as non-tests; no hardcoded credentials remain in tracked scripts | Verified |
| R-33 | Anonymous, read-only public catalogue APIs | `catalog/public_views.py`, `catalog/public_serializers.py`, routes in `catalog/urls.py` | `tests/test_public_catalogue.py` (19 tests): visibility, filters, pagination, security, image URLs | Verified |
| R-34 | Native Android catalogue integration (Test 28 scope still excludes final UI polish) | `MyTrolleyApiService`, `CatalogDtos`, `CatalogPricing`, `CatalogRepository`, `HomeViewModel`, Explore and detail screens | `:app:assembleDebug`, `:app:testDebugUnitTest` (5 tests) and emulator screenshots with real stores/products/images | Verified |
| R-35 | Visibility-checked public image serving | `PublicImageView`, request-aware URLs, `MEDIA_ROOT` | Absolute emulator-friendly URLs; image endpoint returns `image/jpeg` bytes | Verified |

## Evidence commands

```powershell
cd C:\Users\user\OneDrive\Documents\MyTrolleyApp\backend
.\.venv\Scripts\Activate.ps1

python -m ruff check .
python -m ruff format --check .
python -m mypy .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --file openapi.yaml
python -m pytest --cov --cov-report=term-missing --cov-report=xml
python -m pip_audit -r requirements\production.txt
python -m pip_audit -r requirements\development.txt
```

Production deploy check (values are placeholders; use real secrets at deployment time):

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
