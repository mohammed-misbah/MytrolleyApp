"""Base Django settings shared by every environment.

Environment-specific modules must set DEBUG and security flags explicitly.
Importing this module requires a valid DJANGO_SECRET_KEY and database
configuration; failures name the variable but never print its value.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from config.env import (
    get_admin_path,
    get_bool,
    get_db_identifier,
    get_env,
    get_int,
    get_jwt_signing_key,
    get_list,
    get_networks,
    get_origins,
    get_secret_key,
    get_sslmode,
    load_env_file,
)

BASE_DIR = Path(__file__).resolve().parents[2]

# Load backend/.env for local development. Existing process variables win.
load_env_file(BASE_DIR / ".env")

SECRET_KEY = get_secret_key()

# Never opt into DEBUG via the environment. Development settings override this.
DEBUG = False

ALLOWED_HOSTS = get_list(
    "DJANGO_ALLOWED_HOSTS",
    default=("localhost", "127.0.0.1", "[::1]"),
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "accounts",
    "core",
    "catalog",
]

MIDDLEWARE = [
    # Request ID must run before anything that can log.
    "core.middleware.RequestIdMiddleware",
    # Outer logging wrapper captures handled and unhandled failures.
    "core.middleware.RequestLoggingMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.AdminIpAllowlistMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DB_NAME = get_db_identifier("DB_NAME")
DB_TEST_NAME = get_db_identifier(
    "TEST_DB_NAME",
    default=f"test_{DB_NAME}",
)
DB_SSLMODE = get_sslmode("DB_SSLMODE", default="prefer")
DB_CONNECT_TIMEOUT = get_int(
    "DB_CONNECT_TIMEOUT",
    default=5,
    minimum=1,
    maximum=30,
)
DB_SSLROOTCERT = get_env("DB_SSLROOTCERT").strip()

_db_options: dict[str, object] = {
    "connect_timeout": DB_CONNECT_TIMEOUT,
    "sslmode": DB_SSLMODE,
}
if DB_SSLROOTCERT:
    root_cert = Path(DB_SSLROOTCERT)
    if not root_cert.is_absolute():
        root_cert = BASE_DIR / root_cert
    _db_options["sslrootcert"] = str(root_cert)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": DB_NAME,
        "USER": get_env("DB_USER", required=True),
        "PASSWORD": get_env("DB_PASSWORD", required=True),
        "HOST": get_env("DB_HOST", default="127.0.0.1"),
        "PORT": get_int("DB_PORT", default=5432, minimum=1, maximum=65535),
        "CONN_MAX_AGE": get_int(
            "DB_CONN_MAX_AGE",
            default=0,
            minimum=0,
            maximum=3600,
        ),
        "CONN_HEALTH_CHECKS": True,
        # Explicit service/manage.py transactions keep request scopes short.
        "ATOMIC_REQUESTS": False,
        "OPTIONS": _db_options,
        "TEST": {"NAME": DB_TEST_NAME},
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": ("django.contrib.auth.password_validation.UserAttributeSimilarityValidator"),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Uploaded catalogue images live under BASE_DIR (e.g. products/<id>/images/...).
# An explicit root keeps ImageField.path absolute regardless of the working
# directory used to start the server. No public URL prefix is exposed here;
# images are served only through the visibility-checked public image endpoint.
MEDIA_ROOT = BASE_DIR
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Sessions and CSRF
# ---------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "sessionid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 28_800  # 8 hours, sliding; see docs/security.md
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_HTTPONLY = False  # The browser must echo this value in X-CSRFToken.
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_USE_SESSIONS = False
CSRF_TRUSTED_ORIGINS = get_origins("CSRF_TRUSTED_ORIGINS")
CSRF_FAILURE_VIEW = "config.views.csrf_failure"

# ---------------------------------------------------------------------------
# Security headers and proxy assumptions
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

TRUST_PROXY_HEADERS = get_bool("TRUST_PROXY_HEADERS", default=False)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if TRUST_PROXY_HEADERS else None
USE_X_FORWARDED_HOST = False

# ---------------------------------------------------------------------------
# JWT authentication
# ---------------------------------------------------------------------------
# Access token lifetime (default 5 min). Refresh token lifetime (default 1 day).
# Absolute session limit: rotation never extends beyond this value (default 7 days).
JWT_ACCESS_TOKEN_LIFETIME_SECONDS = get_int(
    "JWT_ACCESS_TOKEN_LIFETIME_SECONDS",
    default=300,
    minimum=30,
    maximum=3600,
)

JWT_REFRESH_TOKEN_LIFETIME_SECONDS = get_int(
    "JWT_REFRESH_TOKEN_LIFETIME_SECONDS",
    default=86400,
    minimum=300,
    maximum=604_800,
)
JWT_ABSOLUTE_SESSION_SECONDS = get_int(
    "JWT_ABSOLUTE_SESSION_SECONDS",
    default=604_800,
    minimum=3600,
    maximum=2_592_000,
)
# Cookie refresh is authorized by an ambient cookie, so it also requires the
# CSRF cookie. That cookie must outlive the refresh cookie or an idle browser
# could not refresh; tie it to the hard session cap.
CSRF_COOKIE_AGE = JWT_ABSOLUTE_SESSION_SECONDS
JWT_ISSUER = "mytrolley-api"
JWT_AUDIENCE = "mytrolley-api"
# Validated at startup: at least 50 characters and never equal to SECRET_KEY.
JWT_SIGNING_KEY = get_jwt_signing_key()

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(seconds=JWT_ACCESS_TOKEN_LIFETIME_SECONDS),
    "REFRESH_TOKEN_LIFETIME": timedelta(seconds=JWT_REFRESH_TOKEN_LIFETIME_SECONDS),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "VERIFYING_KEY": JWT_SIGNING_KEY,
    "AUDIENCE": JWT_AUDIENCE,
    "ISSUER": JWT_ISSUER,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": (
        "rest_framework_simplejwt.authentication.default_user_authentication_rule"
    ),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
}

# ---------------------------------------------------------------------------
# API and request-size limits
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.SessionAwareJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "core.parsers.BoundedJSONParser",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "EXCEPTION_HANDLER": "core.exception_handler.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # No process-local throttle classes. Login abuse protection is PostgreSQL-backed.
    "DEFAULT_THROTTLE_CLASSES": [],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MyTrolley API",
    "VERSION": "1.0.0",
    "DESCRIPTION": (
        "JWT Bearer authentication for the MyTrolley API.\n\n"
        "1. `POST /api/v1/auth/login/` with a username and password.\n"
        "2. Click **Authorize** and paste only the **access** token.\n"
        "3. Protected endpoints send `Authorization: Bearer <access>`.\n\n"
        "Access tokens are short-lived. Browsers renew them automatically with "
        "the HttpOnly refresh cookie; that endpoint is intentionally not listed "
        "here. Logout revokes every session for the caller immediately. The "
        "access token is held in memory only and is never written to browser "
        "storage. Errors use the documented `error` envelope."
    ),
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "SWAGGER_UI_SETTINGS": {
        # Tokens live only in the Swagger page's memory. Reloading requires
        # pasting the access token again; nothing is persisted in storage.
        "persistAuthorization": False,
        "withCredentials": False,
        "tryItOutEnabled": True,
        "deepLinking": True,
        "displayRequestDuration": True,
    },
}

MAX_JSON_BODY_BYTES = get_int(
    "MAX_JSON_BODY_BYTES",
    default=65_536,
    minimum=1_024,
    maximum=1_048_576,
)
DATA_UPLOAD_MAX_MEMORY_SIZE = 262_144
FILE_UPLOAD_MAX_MEMORY_SIZE = 262_144
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100
DATA_UPLOAD_MAX_NUMBER_FILES = 10
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750

APPEND_SLASH = False

# ---------------------------------------------------------------------------
# Login abuse protection (database-backed, shared across processes)
# ---------------------------------------------------------------------------
LOGIN_THROTTLE_USERNAME_LIMIT = get_int(
    "LOGIN_THROTTLE_USERNAME_LIMIT",
    default=10,
    minimum=1,
    maximum=1000,
)
LOGIN_THROTTLE_IP_LIMIT = get_int(
    "LOGIN_THROTTLE_IP_LIMIT",
    default=20,
    minimum=1,
    maximum=5000,
)
LOGIN_THROTTLE_WINDOW_SECONDS = get_int(
    "LOGIN_THROTTLE_WINDOW_SECONDS",
    default=900,
    minimum=60,
    maximum=86_400,
)
LOGIN_THROTTLE_COOLDOWN_SECONDS = get_int(
    "LOGIN_THROTTLE_COOLDOWN_SECONDS",
    default=900,
    minimum=60,
    maximum=86_400,
)

# Refresh volume limits are deliberately generous: a legitimate client rotates
# once per access-token lifetime (about 12 times per hour), while the limits
# stop a compromised token from being hammered.
REFRESH_THROTTLE_USER_LIMIT = get_int(
    "REFRESH_THROTTLE_USER_LIMIT",
    default=120,
    minimum=1,
    maximum=10_000,
)
REFRESH_THROTTLE_IP_LIMIT = get_int(
    "REFRESH_THROTTLE_IP_LIMIT",
    default=300,
    minimum=1,
    maximum=20_000,
)
REFRESH_THROTTLE_WINDOW_SECONDS = get_int(
    "REFRESH_THROTTLE_WINDOW_SECONDS",
    default=900,
    minimum=60,
    maximum=86_400,
)
REFRESH_THROTTLE_COOLDOWN_SECONDS = get_int(
    "REFRESH_THROTTLE_COOLDOWN_SECONDS",
    default=900,
    minimum=60,
    maximum=86_400,
)

HEALTH_DB_STATEMENT_TIMEOUT_MS = get_int(
    "HEALTH_DB_STATEMENT_TIMEOUT_MS",
    default=2_000,
    minimum=100,
    maximum=10_000,
)

# ---------------------------------------------------------------------------
# Admin and API documentation exposure
# ---------------------------------------------------------------------------
ADMIN_URL = get_admin_path()
ADMIN_ALLOWED_IPS = get_networks("ADMIN_ALLOWED_IPS")
ENABLE_API_DOCS = get_bool("ENABLE_API_DOCS", default=False)
# Development enables this so Swagger can be opened anonymously for login
# testing. Production forces it to false, so the docs remain staff-only there.
API_DOCS_PUBLIC = get_bool("API_DOCS_PUBLIC", default=False)

# ---------------------------------------------------------------------------
# Logging: structured JSON to stdout, no request bodies or credentials.
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "core.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.db.backends": {"level": "WARNING", "propagate": True},
        "django.request": {"level": "WARNING", "propagate": True},
        "django.security": {"level": "WARNING", "propagate": True},
        "mytrolley": {"level": "INFO", "propagate": True},
    },
}
