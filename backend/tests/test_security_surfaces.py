"""Admin, API documentation and request-logging protections."""

from __future__ import annotations

import json
import logging
import sys

import pytest
from django.test import Client, override_settings

from core.context import reset_request_id, set_request_id
from core.logging import JsonFormatter
from tests.conftest import login, make_user


@pytest.mark.django_db
def test_django_admin_is_staff_only(client: Client, roles) -> None:
    anonymous = client.get("/admin/")
    assert anonymous.status_code == 302
    assert "/admin/login/" in anonymous["Location"]

    staff = make_user("staff-only", is_staff=True)
    client.force_login(staff)
    assert client.get("/admin/").status_code == 200

    non_staff = make_user("not-staff")
    client.force_login(non_staff)
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


@pytest.mark.django_db
@override_settings(ADMIN_ALLOWED_IPS=("10.0.0.0/8",))
def test_admin_ip_allowlist_blocks_other_networks(client: Client) -> None:
    blocked = client.get("/admin/", REMOTE_ADDR="203.0.113.9")
    assert blocked.status_code == 403
    assert "Forbidden" in blocked.content.decode()

    allowed = client.get("/admin/", REMOTE_ADDR="10.4.5.6")
    assert allowed.status_code == 302


@pytest.mark.django_db
def test_openapi_documentation_is_staff_only(client: Client, roles) -> None:
    anonymous = client.get("/api/v1/schema/")
    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "UNAUTHENTICATED"

    staff = make_user("docs-staff", is_staff=True)
    client.force_login(staff)
    schema_response = client.get("/api/v1/schema/")
    assert schema_response.status_code == 200

    docs_response = client.get("/api/v1/docs/")
    assert docs_response.status_code == 200


def test_json_formatter_includes_structured_fields_and_traceback() -> None:
    formatter = JsonFormatter()
    try:
        raise RuntimeError("diagnostic boom")
    except RuntimeError:
        record = logging.LogRecord(
            name="mytrolley.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="something_failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    record.event = "test.event"
    record.method = "POST"
    record.path = "/api/v1/auth/login/"
    record.status = 500
    record.duration_ms = 1.25
    record.password = "must-not-appear"
    token = set_request_id("request-log-test")
    try:
        payload = json.loads(formatter.format(record))
    finally:
        reset_request_id(token)

    assert payload["event"] == "test.event"
    assert payload["request_id"] == "request-log-test"
    assert payload["method"] == "POST"
    assert payload["status"] == 500
    assert "RuntimeError: diagnostic boom" in payload["exception"]
    assert "must-not-appear" not in json.dumps(payload)


@pytest.mark.django_db
def test_login_password_is_not_logged(client: Client, caplog, roles) -> None:
    make_user("log-target")
    caplog.set_level(logging.INFO)

    response = login(client, "log-target", "Never-Log-This-Password-99!")

    assert response.status_code == 401
    assert "Never-Log-This-Password-99!" not in caplog.text
    assert "auth.login.failed" in caplog.text
