"""Client-IP trust rules and Django-level JSON error handlers."""

from __future__ import annotations

import json

import pytest
from django.http import HttpRequest
from django.test import RequestFactory, override_settings

from config.views import (
    bad_request,
    csrf_failure,
    page_not_found,
    permission_denied,
    server_error,
)
from core.middleware import _ip_is_allowed
from core.security import get_client_ip


def _request(*, remote: str = "198.51.100.7", forwarded: str | None = None):
    extra = {"REMOTE_ADDR": remote}
    if forwarded is not None:
        extra["HTTP_X_FORWARDED_FOR"] = forwarded
    return RequestFactory().get("/", **extra)


def test_socket_peer_is_used_without_proxy_trust() -> None:
    assert get_client_ip(_request(remote="203.0.113.8")) == "203.0.113.8"
    assert get_client_ip(_request(remote="not-an-ip")) == "not-an-ip"
    assert get_client_ip(HttpRequest()) == "unknown"


@override_settings(TRUST_PROXY_HEADERS=True)
def test_forwarded_header_uses_last_hop_when_enabled() -> None:
    request = _request(remote="10.0.0.4", forwarded="198.51.100.1, 203.0.113.9")
    assert get_client_ip(request) == "203.0.113.9"


@override_settings(TRUST_PROXY_HEADERS=False)
def test_forwarded_header_is_ignored_when_proxy_trust_disabled() -> None:
    request = _request(remote="10.0.0.4", forwarded="203.0.113.9")
    assert get_client_ip(request) == "10.0.0.4"


@override_settings(TRUST_PROXY_HEADERS=True)
def test_malformed_forwarded_header_falls_back_to_peer() -> None:
    request = _request(remote="10.0.0.4", forwarded="not-an-ip")
    assert get_client_ip(request) == "10.0.0.4"


def test_admin_network_matching_rejects_invalid_inputs() -> None:
    assert _ip_is_allowed("10.1.2.3", ("10.0.0.0/8",))
    assert not _ip_is_allowed("192.0.2.5", ("10.0.0.0/8",))
    assert not _ip_is_allowed("not-an-ip", ("10.0.0.0/8",))
    assert not _ip_is_allowed("10.1.2.3", ("invalid-network",))


@pytest.mark.parametrize(
    ("handler", "code", "status_code"),
    [
        (bad_request, "BAD_REQUEST", 400),
        (permission_denied, "FORBIDDEN", 403),
        (page_not_found, "NOT_FOUND", 404),
        (server_error, "INTERNAL_ERROR", 500),
    ],
)
def test_api_error_handlers_use_the_shared_envelope(
    handler,
    code: str,
    status_code: int,
) -> None:
    request = RequestFactory().get("/api/v1/example/")
    response = handler(request)

    assert response.status_code == status_code
    assert response["Cache-Control"] == "no-store"
    payload = json.loads(response.content)
    assert payload["error"]["code"] == code
    assert payload["error"]["fields"] == {}
    assert response["X-Request-ID"] == payload["error"]["request_id"]


def test_csrf_failure_uses_json_for_api_and_html_for_admin() -> None:
    api_request = RequestFactory().post("/api/v1/auth/login/")
    api_response = csrf_failure(api_request, reason="CSRF cookie not set.")

    assert api_response.status_code == 403
    assert api_response["Content-Type"].startswith("application/json")
    assert json.loads(api_response.content)["error"]["code"] == "CSRF_FAILED"
    assert "CSRF cookie not set." not in api_response.content.decode()

    admin_request = RequestFactory().get("/admin/login/")
    admin_response = csrf_failure(admin_request, reason="CSRF cookie not set.")

    assert admin_response.status_code == 403
    assert admin_response["Content-Type"].startswith("text/html")
