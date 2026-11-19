# MyTrolley — Django backend, React dashboard and native Android catalogue

The repository now contains the full product-discovery stack:

- **Backend:** Django 5.2 / DRF / PostgreSQL with authenticated administrative
  catalogue APIs and a separate anonymous, read-only public catalogue.
- **React dashboard:** `frontend/` manages categories, stores, products,
  attributes, images, store-specific pricing and soft deletion using the
  authenticated APIs.
- **Native Android:** `C:\Users\user\AndroidStudioProjects\MyTrolley` (outside
  this repository) browses the public catalogue with no customer login.

The original Milestone 1 foundation (JWT auth, roles, health, error envelope)
remains in place and unchanged.

- **Stack:** Python 3.14, Django 5.2 LTS, Django REST Framework, PostgreSQL 14+
- **Location:** `C:\Users\user\OneDrive\Documents\MyTrolleyApp\`
- **Runtime settings:** `config.settings.development` (default) and `config.settings.production`
- **Test settings:** `config.settings.test`
- **API docs:** OpenAPI schema and Swagger UI (`/api/v1/schema/`, `/api/v1/docs/`); staff-only in production, anonymously reachable by default in development

## Public catalogue (anonymous, read-only)

These endpoints require **no** login and accept only `GET`, `HEAD` and `OPTIONS`:

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/public/stores/` | Active stores with public product counts |
| `GET /api/v1/public/categories/` | Active, publicly visible categories |
| `GET /api/v1/public/products/` | Paginated, searchable/filterable public product list |
| `GET /api/v1/public/products/{id}/` | Public product detail with attributes, images and store offers |
| `GET /api/v1/public/images/{id}/` | Visibility-checked image bytes (request-aware absolute URLs) |

Query parameters for the product list: `search`, `category`, `store`, `page`,
`page_size` (max 100), `ordering` (`price` requires `store`), `min_price` and
`max_price` (require `store`). `is_active`, `is_available` and `deleted_at`
are rejected with `400 VALIDATION_ERROR`; they cannot relax visibility.

A product is public only when it is active, not soft-deleted, its category and
all ancestors are active, and it has at least one available association with
an active store. Prices and quantities always come from the selected
product-store association; there is no global price.

Administrative endpoints under `/api/v1/stores/`, `/api/v1/categories/` and
`/api/v1/products/` still require a Bearer access token plus the
`accounts.manage_catalog` permission.

### Running the stack locally

```powershell
# Backend (bind to all interfaces so the Android emulator can reach it)
cd C:\Users\user\OneDrive\Documents\MyTrolleyApp\backend
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000 --noreload

# React dashboard
cd ..\frontend
npm run dev

# Android (JDK 25 is bundled with Android Studio)
cd C:\Users\user\AndroidStudioProjects\MyTrolley
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat :app:assembleDebug
```

The Android debug build defaults to `http://10.0.2.2:8000/api/v1/`, the
standard emulator-to-host alias. If the emulator routes app traffic through a
different interface, override it at build time, for example
`-PmytrolleyApiUrl=http://192.168.1.147:8000/api/v1/`, and include that host
in `DJANGO_ALLOWED_HOSTS` in `backend/.env`. Cleartext HTTP is permitted only
for these development hosts in the debug build; release builds do not enable
unrestricted cleartext.

### Verification commands

```powershell
cd C:\Users\user\OneDrive\Documents\MyTrolleyApp\backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q tests/test_public_catalogue.py
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py spectacular --validate
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy .

cd ..\frontend
npm run typecheck
npm run build

cd C:\Users\user\AndroidStudioProjects\MyTrolley
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat :app:testDebugUnitTest
```

Health endpoints are `/api/v1/health/live/` and `/api/v1/health/ready/`.
Requests to `/health` are not part of this application.

## Repository layout

```text
MyTrolleyApp/
├── backend/
│   ├── config/                 Django settings, URLs, env validation, error views
│   ├── accounts/               custom user, roles, auth API, login throttling
│   ├── core/                   error envelope, middleware, health, parsers, docs
│   ├── tests/                  pytest integration and unit tests
│   ├── requirements/           pinned base/development/production dependencies
│   ├── .env.example            placeholders only; copy to .env
│   ├── manage.py
│   └── pyproject.toml          Ruff, mypy, pytest and coverage configuration
├── docs/
│   ├── api.md                  endpoint contracts, JWT/CSRF and public catalogue
│   ├── architecture.md         components, ERD, trust boundaries, future design
│   ├── frontend-integration.md browser token storage and refresh serialization
│   ├── jwt_migration_plan.md   JWT migration decisions and rollback
│   ├── requirements-traceability.md
│   ├── security.md             threat model and controls
│   └── verification.md         commands, results and known limitations
├── frontend/                   React/Vite admin dashboard (npm run dev / build)
├── .github/workflows/ci.yml
├── .gitignore
└── README.md
```

The pre-existing Node diet-planner project in `Default Project` is untouched and
unrelated to this backend.

## Prerequisites

- Python **3.14** on `PATH`
- PostgreSQL **14 or newer** running locally
- PowerShell 7 or Windows PowerShell 5.1
- A PostgreSQL login that can create the application database

## Local setup (Windows / PowerShell)

```powershell
cd C:\Users\user\OneDrive\Documents\MyTrolleyApp\backend

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements\development.txt

Copy-Item .env.example .env
notepad .env    # set DJANGO_SECRET_KEY, DB_PASSWORD and other local values
```

Create the database and role once. Replace the placeholder password with your
own local value; do not commit it.

```sql
-- Run in psql as a PostgreSQL administrator:
CREATE ROLE mytrolley_app LOGIN PASSWORD 'replace-with-a-local-password';
CREATE DATABASE mytrolley OWNER mytrolley_app;
```

Then run migrations and provision the two assessment roles plus your own
initial administrator. There is no default account and no public registration.

```powershell
python manage.py migrate
python manage.py seed_roles
python manage.py create_initial_admin
python manage.py runserver
```

`create_initial_admin` prompts for username, email and password with
`getpass`; passwords are never accepted as command-line arguments.

Health checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live/
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready/
```

## Roles and permissions

| Role | Group | Business permissions | Intended use |
|---|---|---|---|
| Administrator | `Administrator` | `accounts.manage_users`, `accounts.manage_catalog` | Full assessment administration |
| Data-entry | `DataEntry` | `accounts.manage_catalog` | Catalog/product data entry only |
| Authenticated but ungrouped | — | none | Denied by business-permission checks |

Roles are Django groups, permissions are Django permissions, and seeding is
idempotent. `accounts.manage_users` and `accounts.manage_catalog` are the only
business permissions exposed in the current API surface. Milestone 1 does not
provide user-management or product endpoints; the permission class and test
URLs prove the authorization pattern for later milestones.

## API surface

All API responses are JSON. Errors use one envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Please correct the supplied values.",
    "fields": {"username": ["This field is required."]},
    "request_id": "5f0c2d9a7b1e4c3a8d6f0e2b4c6a8d0e"
  }
}
```

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/login/` | Public | Issue an access token, HttpOnly refresh cookie and readable CSRF cookie |
| POST | `/api/v1/auth/refresh/` | Cookie + CSRF or body token | Rotate the access/refresh pair; hidden from Swagger UI |
| POST | `/api/v1/auth/logout/` | Authenticated | Revoke all caller sessions, clear cookie, return 200 |
| GET | `/api/v1/auth/me/` | Authenticated | Safe current-user profile, roles, permissions |
| GET | `/api/v1/health/live/` | Public | Process liveness; no database access |
| GET | `/api/v1/health/ready/` | Public | Bounded PostgreSQL readiness query |
| GET | `/api/v1/schema/` | Staff only (development: public) | OpenAPI 3 schema |
| GET | `/api/v1/docs/` | Staff only (development: public) | Swagger UI |
| any | `/{ADMIN_URL}` | Staff only | Django admin |

Authentication uses short-lived JWT access tokens. Login returns the access
token and safe profile in JSON and sets the refresh token as an `HttpOnly`
cookie; the refresh token is never returned in JSON. Send
`Authorization: Bearer <access>` on protected endpoints. Cookie-based refresh
requires `X-CSRFToken` echoed from the `csrftoken` cookie that login sets; a
body-supplied refresh token does not. Bearer-only requests need no CSRF token.
Refresh rotates and detects replay, revoking the affected token family. Logout
revokes every session for the caller and returns `200` with an explicit
message. See [docs/api.md](docs/api.md) for request examples and
[docs/frontend-integration.md](docs/frontend-integration.md) for browser token
handling.

### Test the auth API with Swagger UI

Development exposes the existing drf-spectacular Swagger UI without requiring a
staff login, so a genuinely anonymous login can be tested. Start the server and
open:

```text
http://127.0.0.1:8000/api/v1/docs/
```

Then:

1. Expand **Authentication**.
2. `POST /api/v1/auth/login/` → **Execute** with
   `{"username": "your-username", "password": "your-password"}`. Expect `200`
   with `access` and `user`; the refresh cookie is set silently.
3. Click **Authorize**, paste only the `access` value and confirm.
4. `GET /api/v1/auth/me/` → **Execute**. Expect `200` and your user.
5. `POST /api/v1/auth/logout/` → **Execute**. Expect `200` and
   `{"message": "Logout successful. All active sessions for the current user have been revoked."}`.
6. Run `me` again. Expect `401 SESSION_REVOKED`.

The refresh endpoint is intentionally hidden from Swagger UI but remains
callable; exercise it with a cookie jar or send the refresh token in a JSON body
(see [docs/api.md](docs/api.md#post-apiv1authrefresh)). To require staff access
locally, set `API_DOCS_PUBLIC=false` in `backend/.env` and restart the server.
Production always forces it to false.

## Quality gates

Run from `backend/` with the virtual environment active and PostgreSQL
available:

```powershell
python -m ruff check accounts core config tests\test_auth.py tests\test_jwt_security.py tests\test_swagger_docs.py tests\test_errors.py tests\test_throttling.py tests\test_permissions.py tests\test_security_surfaces.py tests\test_commands.py tests\conftest.py
python -m ruff format --check accounts core config tests\test_auth.py tests\test_jwt_security.py tests\test_swagger_docs.py tests\test_errors.py tests\test_throttling.py tests\test_permissions.py tests\test_security_surfaces.py tests\test_commands.py tests\conftest.py
python -m mypy accounts core config
python -m pytest --cov --cov-report=term-missing --ignore=tests/test_catalog_api.py --ignore=tests/test_catalog_models.py
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --file openapi.yaml
python -m pip_audit -r requirements\production.txt
```

Test settings use PostgreSQL, not SQLite. The default test database name is
`test_<DB_NAME>`; override it with `TEST_DB_NAME`. Coverage fails below **85%**.
Latest local authentication-slice verification: **157 tests passed, 94.52%
total coverage**. The two `catalog` test modules are Milestone 2 work in
progress and are not part of this milestone; they are excluded from the
authentication-slice run and still block a clean repo-wide Ruff/collection run.
See [verification](docs/verification.md) for the exact environment, commands and
remaining blockers.

Production configuration is validated at startup. A representative deploy
check requires production values, for example:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
$env:DJANGO_SECRET_KEY = "<unique 50+ character value>"
$env:JWT_SIGNING_KEY = "<different unique 50+ character value>"
$env:DJANGO_ALLOWED_HOSTS = "api.example.test"
$env:CSRF_TRUSTED_ORIGINS = "https://app.example.test"
$env:SECURE_HSTS_SECONDS = "31536000"
$env:DB_SSLMODE = "require"
$env:ADMIN_URL = "ops-admin/"
python manage.py check --deploy
```

Milestone 1 was verified against the local PostgreSQL 14.18 service on
`127.0.0.1:5432`, including a live HTTP smoke test and a Swagger UI browser run.
The JWT changes are uncommitted, so no GitHub Actions run exists for them; the
workflow itself is in `.github/workflows/ci.yml`. See
[docs/verification.md](docs/verification.md) for exact commands, results and
blockers.

## Documentation

- [API contract](docs/api.md)
- [Architecture, ERD, trust boundaries and future design](docs/architecture.md)
- [Frontend JWT integration](docs/frontend-integration.md)
- [JWT migration record](docs/jwt_migration_plan.md)
- [Security controls and threat model](docs/security.md)
- [Requirements traceability](docs/requirements-traceability.md)
- [Verification results and limitations](docs/verification.md)

## Milestone boundaries

Implemented in milestone 1:

- Custom user before the first migration; no default credentials
- JWT access tokens with server-side session revocation
- Rotating refresh cookies, reuse detection and CSRF on cookie renewal
- Single logout endpoint that revokes all caller sessions and returns 200
- Groups/permissions with default-deny DRF policy
- PostgreSQL-backed login abuse protection shared across processes
- Health endpoints, centralized errors, request IDs, structured logging
- Production settings validation and security headers
- OpenAPI documentation, tests, coverage, lint/type checks and CI

Not implemented in milestone 1 (planned later):

- React dashboard and Swift client
- Product/catalog CRUD, categories, image upload/storage
- Store and price comparison
- Shopping-list logic and totals
- Deployment automation, TLS termination and production infrastructure
