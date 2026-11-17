"""Pure configuration parsing and production validation."""

from __future__ import annotations

from dataclasses import replace

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.env import (
    get_admin_path,
    get_bool,
    get_db_identifier,
    get_env,
    get_int,
    get_list,
    get_networks,
    get_origins,
    get_secret_key,
    get_sslmode,
    load_env_file,
)
from config.validation import ProductionConfig, validate_production_config

VALID_PRODUCTION = ProductionConfig(
    debug=False,
    secret_key="v" * 60,
    allowed_hosts=["api.example.test"],
    session_cookie_secure=True,
    csrf_cookie_secure=True,
    ssl_redirect=True,
    hsts_seconds=31_536_000,
    hsts_include_subdomains=True,
    hsts_preload=False,
    db_sslmode="verify-full",
    db_sslrootcert="/etc/ssl/certs/provider-ca.pem",
    admin_url="ops-admin/",
    csrf_trusted_origins=["https://app.example.test"],
    trust_proxy_headers=True,
    secure_proxy_ssl_header=True,
)


def test_env_file_loading_and_process_precedence(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "FIRST_VALUE=from-file\n"
        'QUOTED="quoted value"\n'
        "export EXPORTED='exported value'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("FIRST_VALUE", raising=False)
    monkeypatch.delenv("QUOTED", raising=False)
    monkeypatch.delenv("EXPORTED", raising=False)
    monkeypatch.setenv("FIRST_VALUE", "from-process")

    load_env_file(env_file)

    assert get_env("FIRST_VALUE") == "from-process"
    assert get_env("QUOTED") == "quoted value"
    assert get_env("EXPORTED") == "exported value"


def test_env_file_is_optional(tmp_path) -> None:
    load_env_file(tmp_path / "absent.env")


def test_invalid_env_file_line_fails_without_value(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("NOT-A-VALID-LINE-super-secret\n", encoding="utf-8")

    with pytest.raises(ImproperlyConfigured) as exc_info:
        load_env_file(env_file)

    assert "line 1" in str(exc_info.value)
    assert "super-secret" not in str(exc_info.value)


def test_boolean_parsing(monkeypatch) -> None:
    for raw in ("true", "TRUE", "1", "yes", "on"):
        monkeypatch.setenv("BOOL_VALUE", raw)
        assert get_bool("BOOL_VALUE", default=False) is True
    for raw in ("false", "0", "no", "off"):
        monkeypatch.setenv("BOOL_VALUE", raw)
        assert get_bool("BOOL_VALUE", default=True) is False
    monkeypatch.setenv("BOOL_VALUE", "sometimes")
    with pytest.raises(ImproperlyConfigured, match="BOOL_VALUE"):
        get_bool("BOOL_VALUE", default=False)


def test_integer_bounds(monkeypatch) -> None:
    monkeypatch.setenv("PORT_VALUE", "5432")
    assert get_int("PORT_VALUE", default=1, minimum=1, maximum=65535) == 5432
    monkeypatch.setenv("PORT_VALUE", "not-a-number")
    with pytest.raises(ImproperlyConfigured, match="integer"):
        get_int("PORT_VALUE", default=1)
    monkeypatch.setenv("PORT_VALUE", "0")
    with pytest.raises(ImproperlyConfigured, match="at least"):
        get_int("PORT_VALUE", default=1, minimum=1)


def test_required_values_and_lists(monkeypatch) -> None:
    monkeypatch.delenv("REQUIRED_VALUE", raising=False)
    with pytest.raises(ImproperlyConfigured, match="REQUIRED_VALUE"):
        get_env("REQUIRED_VALUE", required=True)

    monkeypatch.setenv("LIST_VALUE", " one, two ,, three ")
    assert get_list("LIST_VALUE") == ["one", "two", "three"]
    monkeypatch.setenv("LIST_VALUE", "  ")
    with pytest.raises(ImproperlyConfigured, match="LIST_VALUE"):
        get_list("LIST_VALUE", required=True)


def test_secret_validation_never_echoes_value(monkeypatch) -> None:
    monkeypatch.setenv("DJANGO_SECRET_KEY", "DO-NOT-LEAK-short")
    with pytest.raises(ImproperlyConfigured) as exc_info:
        get_secret_key()
    assert "DO-NOT-LEAK-short" not in str(exc_info.value)
    assert "at least 50" in str(exc_info.value)

    monkeypatch.setenv(
        "DJANGO_SECRET_KEY",
        "changeme-" + "x" * 60,
    )
    with pytest.raises(ImproperlyConfigured, match="placeholder"):
        get_secret_key()


def test_db_identifier_and_sslmode(monkeypatch) -> None:
    monkeypatch.setenv("DB_NAME", "mytrolley")
    assert get_db_identifier("DB_NAME") == "mytrolley"
    monkeypatch.setenv("DB_NAME", "bad-name;DROP")
    with pytest.raises(ImproperlyConfigured, match="DB_NAME"):
        get_db_identifier("DB_NAME")

    monkeypatch.setenv("DB_SSLMODE", "verify-full")
    assert get_sslmode("DB_SSLMODE", default="prefer") == "verify-full"
    monkeypatch.setenv("DB_SSLMODE", "bogus")
    with pytest.raises(ImproperlyConfigured, match="DB_SSLMODE"):
        get_sslmode("DB_SSLMODE", default="prefer")


def test_origin_validation(monkeypatch) -> None:
    monkeypatch.setenv(
        "CSRF_TRUSTED_ORIGINS",
        "https://app.example.test, http://localhost:5173/",
    )
    assert get_origins("CSRF_TRUSTED_ORIGINS") == [
        "https://app.example.test",
        "http://localhost:5173",
    ]
    for invalid in (
        "https://*.example.test",
        "https://user:pass@example.test",
        "https://example.test/path",
    ):
        monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", invalid)
        with pytest.raises(ImproperlyConfigured, match="CSRF_TRUSTED_ORIGINS"):
            get_origins("CSRF_TRUSTED_ORIGINS")


def test_admin_path_normalization_and_validation(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_URL", "ops-admin/")
    assert get_admin_path() == "ops-admin/"
    monkeypatch.setenv("ADMIN_URL", "admin")
    assert get_admin_path() == "admin/"
    monkeypatch.setenv("ADMIN_URL", "../secret/")
    with pytest.raises(ImproperlyConfigured, match="ADMIN_URL"):
        get_admin_path()


def test_network_allowlist_validation(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_ALLOWED_IPS", "10.0.0.0/8, 2001:db8::/32")
    assert get_networks("ADMIN_ALLOWED_IPS") == ("10.0.0.0/8", "2001:db8::/32")
    monkeypatch.setenv("ADMIN_ALLOWED_IPS", "not-an-ip")
    with pytest.raises(ImproperlyConfigured, match="ADMIN_ALLOWED_IPS"):
        get_networks("ADMIN_ALLOWED_IPS")


def test_valid_production_configuration_passes() -> None:
    validate_production_config(VALID_PRODUCTION)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"debug": True}, "DEBUG"),
        ({"allowed_hosts": ["*"]}, "ALLOWED_HOSTS"),
        ({"session_cookie_secure": False}, "SESSION_COOKIE_SECURE"),
        ({"csrf_cookie_secure": False}, "CSRF_COOKIE_SECURE"),
        ({"ssl_redirect": False}, "SECURE_SSL_REDIRECT"),
        ({"db_sslmode": "prefer"}, "DB_SSLMODE"),
        ({"db_sslmode": "verify-full", "db_sslrootcert": None}, "DB_SSLROOTCERT"),
        ({"admin_url": "admin/"}, "ADMIN_URL"),
        ({"csrf_trusted_origins": ["http://app.example.test"]}, "https"),
        ({"trust_proxy_headers": True, "secure_proxy_ssl_header": False}, "TRUST_PROXY"),
        (
            {
                "hsts_preload": True,
                "hsts_include_subdomains": False,
                "hsts_seconds": 3600,
            },
            "HSTS",
        ),
    ],
)
def test_invalid_production_configuration(change, expected) -> None:
    config = replace(VALID_PRODUCTION, **change)
    with pytest.raises(ImproperlyConfigured) as exc_info:
        validate_production_config(config)
    assert expected in str(exc_info.value)


def test_production_validation_does_not_echo_secret() -> None:
    config = replace(
        VALID_PRODUCTION,
        secret_key="DO-NOT-LEAK-" + "x" * 20,
        debug=True,
    )
    with pytest.raises(ImproperlyConfigured) as exc_info:
        validate_production_config(config)
    assert "DO-NOT-LEAK" not in str(exc_info.value)
