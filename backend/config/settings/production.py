"""Production settings with explicit secure configuration.

There are no secret fallbacks and no insecure security defaults here. Invalid
production configuration fails at startup with variable names only.
"""

from __future__ import annotations

from config.env import (
    get_bool,
    get_env,
    get_int,
    get_list,
    get_origins,
    get_sslmode,
)
from config.settings.base import *  # noqa: F403
from config.validation import ProductionConfig, validate_production_config

DEBUG = False

ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", required=True)
CSRF_TRUSTED_ORIGINS = get_origins("CSRF_TRUSTED_ORIGINS")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = get_int(
    "SECURE_HSTS_SECONDS",
    required=True,
    minimum=0,
    maximum=63_072_000,
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_HSTS_PRELOAD = get_bool("SECURE_HSTS_PRELOAD", default=False)

# Long-lived connections are appropriate behind a persistent WSGI server.
DATABASES["default"]["CONN_MAX_AGE"] = get_int(  # noqa: F405
    "DB_CONN_MAX_AGE",
    default=60,
    minimum=0,
    maximum=3600,
)

# If a controlled reverse proxy terminates TLS, trust only its forwarded
# protocol header. The proxy must overwrite client-supplied values.
TRUST_PROXY_HEADERS = get_bool("TRUST_PROXY_HEADERS", default=False)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if TRUST_PROXY_HEADERS else None

# Production docs are disabled unless explicitly enabled, and are always
# staff-only. Restrict them at the network layer as well when enabled.
ENABLE_API_DOCS = get_bool("ENABLE_API_DOCS", default=False)
API_DOCS_PUBLIC = False

DB_SSLMODE = get_sslmode("DB_SSLMODE", default="")

validate_production_config(
    ProductionConfig(
        debug=DEBUG,
        secret_key=SECRET_KEY,  # noqa: F405
        allowed_hosts=ALLOWED_HOSTS,
        session_cookie_secure=SESSION_COOKIE_SECURE,  # noqa: F405
        csrf_cookie_secure=CSRF_COOKIE_SECURE,  # noqa: F405
        ssl_redirect=SECURE_SSL_REDIRECT,  # noqa: F405
        hsts_seconds=SECURE_HSTS_SECONDS,  # noqa: F405
        hsts_include_subdomains=SECURE_HSTS_INCLUDE_SUBDOMAINS,  # noqa: F405
        hsts_preload=SECURE_HSTS_PRELOAD,  # noqa: F405
        db_sslmode=DB_SSLMODE,
        db_sslrootcert=get_env("DB_SSLROOTCERT").strip() or None,
        admin_url=ADMIN_URL,  # noqa: F405
        csrf_trusted_origins=CSRF_TRUSTED_ORIGINS,
        trust_proxy_headers=TRUST_PROXY_HEADERS,
        secure_proxy_ssl_header=bool(SECURE_PROXY_SSL_HEADER),
    )
)
