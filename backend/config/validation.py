"""Pure production configuration validation.

Keeping these checks in a small function makes them unit-testable without
importing the production settings module or touching a database.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

_SAFE_PROXY_SSLMODES = frozenset({"require", "verify-ca", "verify-full"})
_DEFAULT_ADMIN_PATHS = frozenset({"admin/", "django-admin/"})
_MIN_HSTS_FOR_PRELOAD = 31_536_000


@dataclass(frozen=True, slots=True)
class ProductionConfig:
    """Security-relevant production settings to validate."""

    debug: bool
    secret_key: str
    allowed_hosts: Sequence[str]
    session_cookie_secure: bool
    csrf_cookie_secure: bool
    ssl_redirect: bool
    hsts_seconds: int
    hsts_include_subdomains: bool
    hsts_preload: bool
    db_sslmode: str
    db_sslrootcert: str | None
    admin_url: str
    csrf_trusted_origins: Sequence[str]
    trust_proxy_headers: bool
    secure_proxy_ssl_header: bool


def validate_production_config(config: ProductionConfig) -> None:
    """Raise ``ImproperlyConfigured`` with all safe-to-show production errors."""
    errors: list[str] = []

    if config.debug:
        errors.append("DEBUG must be false in production.")
    if len(config.secret_key) < 50:
        errors.append("DJANGO_SECRET_KEY must be at least 50 characters.")
    if not config.allowed_hosts or any(host.strip() in {"", "*"} for host in config.allowed_hosts):
        errors.append("DJANGO_ALLOWED_HOSTS must list explicit hosts and must not contain '*'.")
    if not config.session_cookie_secure:
        errors.append("SESSION_COOKIE_SECURE must be true in production.")
    if not config.csrf_cookie_secure:
        errors.append("CSRF_COOKIE_SECURE must be true in production.")
    if not config.ssl_redirect:
        errors.append("SECURE_SSL_REDIRECT must be true in production.")
    if config.hsts_seconds < 0:
        errors.append("SECURE_HSTS_SECONDS must not be negative.")
    if config.hsts_preload:
        if not config.hsts_include_subdomains:
            errors.append("SECURE_HSTS_PRELOAD requires SECURE_HSTS_INCLUDE_SUBDOMAINS=true.")
        if config.hsts_seconds < _MIN_HSTS_FOR_PRELOAD:
            errors.append(
                "SECURE_HSTS_PRELOAD requires SECURE_HSTS_SECONDS of at least "
                f"{_MIN_HSTS_FOR_PRELOAD}."
            )
    if config.db_sslmode not in _SAFE_PROXY_SSLMODES:
        errors.append("DB_SSLMODE must be require, verify-ca or verify-full in production.")
    if config.db_sslmode in {"verify-ca", "verify-full"} and not config.db_sslrootcert:
        errors.append("DB_SSLROOTCERT is required when DB_SSLMODE verifies the server.")
    if config.admin_url in _DEFAULT_ADMIN_PATHS:
        errors.append("ADMIN_URL must not use the default 'admin/' path in production.")
    for origin in config.csrf_trusted_origins:
        parts = urlsplit(origin)
        if parts.scheme != "https" or not parts.netloc or "*" in origin:
            errors.append("CSRF_TRUSTED_ORIGINS must contain exact https origins in production.")
            break
    if config.trust_proxy_headers and not config.secure_proxy_ssl_header:
        errors.append("TRUST_PROXY_HEADERS=true requires SECURE_PROXY_SSL_HEADER to be enabled.")

    if errors:
        raise ImproperlyConfigured("Invalid production configuration: " + " ".join(errors))
