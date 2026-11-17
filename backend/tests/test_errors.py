"""Input validation, consistent envelopes, request IDs and unexpected errors."""

from __future__ import annotations

import pytest
from django.test import Client, override_settings

from tests.conftest import fetch_csrf, login, make_user, post_json


def assert_error_shape(body: dict) -> None:
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message", "fields", "request_id"}
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["fields"], dict)
    assert isinstance(error["request_id"], str) and error["request_id"]


@pytest.mark.django_db
def test_unknown_api_path_returns_envelope(client: Client) -> None:
    response = client.get("/api/v1/does-not-exist/")

    assert response.status_code == 404
    assert_error_shape(response.json())
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response["X-Request-ID"] == response.json()["error"]["request_id"]


@pytest.mark.django_db
def test_method_not_allowed_returns_envelope(client: Client) -> None:
    response = client.get("/api/v1/auth/login/")

    assert response.status_code == 405
    assert_error_shape(response.json())
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


@pytest.mark.django_db
def test_malformed_json_returns_generic_invalid_json(
    client: Client,
    administrator,
) -> None:
    token = fetch_csrf(client)
    response = post_json(
        client,
        "/api/v1/auth/login/",
        '{"username": "administrator", "password": ',
        csrf_token=token,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_JSON"
    assert "Expecting" not in response.content.decode()
    assert "json.decoder" not in response.content.decode()


@pytest.mark.django_db
def test_empty_json_object_reports_missing_fields(client: Client, administrator) -> None:
    token = fetch_csrf(client)
    response = post_json(client, "/api/v1/auth/login/", {}, csrf_token=token)

    assert response.status_code == 400
    assert_error_shape(response.json())
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "username" in response.json()["error"]["fields"]
    assert "password" in response.json()["error"]["fields"]


@pytest.mark.django_db
def test_wrong_input_types_are_validation_errors(client: Client, administrator) -> None:
    token = fetch_csrf(client)
    response = post_json(
        client,
        "/api/v1/auth/login/",
        {"username": ["administrator"], "password": {"nested": "value"}},
        csrf_token=token,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "username" in response.json()["error"]["fields"]
    assert "password" in response.json()["error"]["fields"]


@pytest.mark.django_db
def test_unexpected_fields_are_rejected_not_ignored(
    client: Client,
    administrator,
) -> None:
    token = fetch_csrf(client)
    response = post_json(
        client,
        "/api/v1/auth/login/",
        {
            "username": "administrator",
            "password": "Correct-Horse-42!",
            "is_staff": True,
            "groups": ["Administrator"],
        },
        csrf_token=token,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "non_field_errors" in response.json()["error"]["fields"]
    administrator.refresh_from_db()
    assert administrator.is_staff is True  # fixture value, unchanged by payload


@pytest.mark.django_db
def test_oversized_string_is_rejected(client: Client, administrator) -> None:
    token = fetch_csrf(client)
    response = post_json(
        client,
        "/api/v1/auth/login/",
        {"username": "x" * 151, "password": "Correct-Horse-42!"},
        csrf_token=token,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "username" in response.json()["error"]["fields"]


@pytest.mark.django_db
@override_settings(MAX_JSON_BODY_BYTES=1024)
def test_oversized_body_returns_413(client: Client, administrator) -> None:
    token = fetch_csrf(client)
    response = post_json(
        client,
        "/api/v1/auth/login/",
        {"username": "administrator", "password": "x" * 2000},
        csrf_token=token,
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "x" * 100 not in response.content.decode()


@pytest.mark.django_db
def test_unsupported_media_type_returns_415(client: Client, administrator) -> None:
    token = fetch_csrf(client)
    response = client.post(
        "/api/v1/auth/login/",
        data="username=administrator&password=Correct-Horse-42!",
        content_type="application/x-www-form-urlencoded",
        HTTP_X_CSRFTOKEN=token,
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


@pytest.mark.django_db
def test_request_id_validation_and_error_correlation(client: Client) -> None:
    supplied = "client-request-123"
    response = client.get(
        "/api/v1/does-not-exist/",
        HTTP_X_REQUEST_ID=supplied,
    )
    assert response.status_code == 404
    assert response["X-Request-ID"] == supplied
    assert response.json()["error"]["request_id"] == supplied

    response = client.get(
        "/api/v1/does-not-exist/",
        HTTP_X_REQUEST_ID="bad id with spaces",
    )
    generated = response["X-Request-ID"]
    assert generated != "bad id with spaces"
    assert len(generated) == 32
    assert generated == response.json()["error"]["request_id"]


@pytest.mark.django_db
def test_sensitive_values_absent_from_error_response(client: Client, roles) -> None:
    make_user("sensitive-user", password="Sensitive-Password-99!")
    response = login(client, "sensitive-user", "wrong-password")

    text = response.content.decode().lower()
    assert response.status_code == 401
    for secret in ("sensitive-password-99", "sql", "traceback", "psycopg", "password="):
        assert secret not in text


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="tests.urls_for_tests", DEBUG=False)
def test_unexpected_exception_returns_generic_500_and_logs_traceback(
    client: Client,
    caplog,
) -> None:
    response = client.get("/test-only/explode/")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    text = response.content.decode()
    assert "RuntimeError" not in text
    assert "boom" not in text
    assert "Traceback" not in text
    assert "api.unhandled_exception" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "boom" in caplog.text  # server-side diagnostics retain the cause
    assert response["X-Request-ID"] == response.json()["error"]["request_id"]
