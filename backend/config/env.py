"""Environment loading and strict configuration parsing.

Only variable *names* and validation failures are ever included in error
messages. Secret values are never rendered.
"""

from __future__ import annotations

import ipaddress
import os
import re
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

_TRUE_VALUES: Final = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES: Final = frozenset({"0", "false", "no", "off"})
_DB_IDENTIFIER_RE: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_ADMIN_PATH_RE: Final = re.compile(r"^[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*/$")
_INSECURE_SECRET_MARKERS: Final = (
    "django-insecure-",
    "replace-with",
    "changeme",
    "change-me",
    "your-secret",
)
_MIN_SECRET_LENGTH: Final = 50


def load_env_file(path: Path) -> None:
    """Load a simple KEY=VALUE file without overriding real process variables.

    The format deliberately stays small: comments, blank lines, optional
    ``export`` prefixes and matching single/double quotes. Values are not
    printed, including on parse errors.
    """
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ImproperlyConfigured(f"Could not read environment file {path.name}.") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        if "=" not in line:
            raise ImproperlyConfigured(
                f"Invalid environment file {path.name}, line {line_number}: expected KEY=VALUE."
            )
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ImproperlyConfigured(
                f"Invalid environment variable name in {path.name}, line {line_number}."
            )
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        # Real process environment variables take precedence.
        os.environ.setdefault(key, value)


def get_env(
    name: str,
    *,
    default: str | None = None,
    required: bool = False,
) -> str:
    """Return an environment value, failing clearly when required and absent."""
    value = os.environ.get(name)
    if value is None or (required and not value.strip()):
        if required:
            raise ImproperlyConfigured(
                f"{name} is required. Copy backend/.env.example to backend/.env "
                "and fill in local values, or set the process environment variable."
            )
        return "" if default is None else default
    return value


def get_bool(name: str, *, default: bool) -> bool:
    """Parse a boolean environment variable."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ImproperlyConfigured(f"{name} must be one of true/false, 1/0, yes/no or on/off.")


def get_int(
    name: str,
    *,
    default: int | None = None,
    required: bool = False,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Parse and bound an integer environment variable."""
    raw = get_env(name, default=None if default is None else str(default), required=required)
    if not raw.strip():
        raise ImproperlyConfigured(f"{name} must be an integer.")
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer.") from exc
    if minimum is not None and value < minimum:
        raise ImproperlyConfigured(f"{name} must be at least {minimum}.")
    if maximum is not None and value > maximum:
        raise ImproperlyConfigured(f"{name} must be at most {maximum}.")
    return value


def get_list(
    name: str,
    *,
    default: tuple[str, ...] = (),
    required: bool = False,
) -> list[str]:
    """Parse a comma-separated list, dropping empty entries."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        if required:
            raise ImproperlyConfigured(f"{name} is required and must not be empty.")
        return list(default)
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if required and not values:
        raise ImproperlyConfigured(f"{name} is required and must not be empty.")
    return values


def get_secret_key() -> str:
    """Load and validate Django's signing secret without revealing it."""
    value = get_env("DJANGO_SECRET_KEY", required=True).strip()
    if len(value) < _MIN_SECRET_LENGTH:
        raise ImproperlyConfigured(
            f"DJANGO_SECRET_KEY must contain at least {_MIN_SECRET_LENGTH} characters."
        )
    lowered = value.lower()
    if any(marker in lowered for marker in _INSECURE_SECRET_MARKERS):
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY looks like a placeholder or an insecure "
            "development key. Generate a unique random value."
        )
    if len(set(value)) < 10:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY does not have enough variation. Generate a unique random value."
        )
    return value


def get_db_identifier(name: str, *, default: str | None = None) -> str:
    """Validate a PostgreSQL identifier safe to interpolate into a test DB name.

    This value is not interpolated into SQL by application code. It is
    validated because Django derives the test database name from it.
    """
    value = get_env(name, default=default, required=default is None).strip()
    if not _DB_IDENTIFIER_RE.fullmatch(value):
        raise ImproperlyConfigured(
            f"{name} must be 1-63 characters using letters, digits or underscores, "
            "and must not start with a digit."
        )
    return value


def get_sslmode(name: str, *, default: str) -> str:
    """Validate PostgreSQL sslmode."""
    allowed = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
    value = get_env(name, default=default).strip().lower()
    if value not in allowed:
        raise ImproperlyConfigured(f"{name} must be one of: {', '.join(sorted(allowed))}.")
    return value


def get_origins(name: str, *, required: bool = False) -> list[str]:
    """Parse exact CSRF origins. Wildcards, credentials and paths are rejected."""
    origins = get_list(name, required=required)
    normalized: list[str] = []
    for origin in origins:
        if "*" in origin:
            raise ImproperlyConfigured(f"{name} must not contain wildcards.")
        parts = urlsplit(origin)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.netloc
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or parts.path not in {"", "/"}
        ):
            raise ImproperlyConfigured(f"{name} must contain exact scheme://host[:port] origins.")
        normalized.append(f"{parts.scheme}://{parts.netloc}")
    return normalized


def get_admin_path() -> str:
    """Return a safe, normalized admin URL prefix such as ``ops-admin/``."""
    raw = get_env("ADMIN_URL", default="admin/").strip().strip("/")
    if not raw:
        raise ImproperlyConfigured("ADMIN_URL must not be empty.")
    normalized = f"{raw}/"
    if not _ADMIN_PATH_RE.fullmatch(normalized):
        raise ImproperlyConfigured(
            "ADMIN_URL may contain letters, digits, hyphens, underscores and "
            "slash-separated segments, and must not contain '..'."
        )
    return normalized


def get_networks(name: str) -> tuple[str, ...]:
    """Validate exact IP addresses or CIDR networks for an allowlist."""
    entries = get_list(name)
    for entry in entries:
        try:
            ipaddress.ip_network(entry, strict=False)
        except ValueError as exc:
            raise ImproperlyConfigured(
                f"{name} contains an invalid IP address or CIDR network."
            ) from exc
    return tuple(entries)
