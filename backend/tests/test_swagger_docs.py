"""Regression tests for the Swagger UI page and the public OpenAPI schema."""

from __future__ import annotations

import json

import pytest
from django.test import Client
from drf_spectacular.generators import SchemaGenerator

from accounts.views import LOGOUT_SUCCESS_MESSAGE
from tests.conftest import access_token, auth_header, login, make_user


def test_refresh_and_removed_csrf_route_are_absent_from_the_public_schema() -> None:
    """Refresh stays callable but is hidden; the CSRF route no longer exists."""
    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]

    assert "/api/v1/auth/login/" in paths
    assert "/api/v1/auth/logout/" in paths
    assert "/api/v1/auth/me/" in paths
    assert "/api/v1/auth/refresh/" not in paths
    assert "/api/v1/auth/csrf/" not in paths
    # No CSRF header parameter is documented anywhere; the login description
    # only mentions the cookie the browser echoes, which is not a schema input.
    assert '"name": "X-CSRFToken"' not in json.dumps(schema)
    assert schema["components"]["securitySchemes"]["jwtAuth"]["scheme"] == "bearer"

    login_response = schema["paths"]["/api/v1/auth/login/"]["post"]["responses"]["200"]
    schema_name = login_response["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
    assert "refresh" not in schema["components"]["schemas"][schema_name]["properties"]


def test_logout_documents_the_message_the_server_returns() -> None:
    """The documented 200 body must match the implemented contract."""
    schema = SchemaGenerator().get_schema(request=None, public=True)
    documented = json.dumps(schema["paths"]["/api/v1/auth/logout/"]["post"]["responses"]["200"])

    assert LOGOUT_SUCCESS_MESSAGE in documented
    assert "logout-all" not in json.dumps(schema)


@pytest.mark.django_db
def test_swagger_ui_renders_without_template_errors(client: Client) -> None:
    """The docs page must render with the stock drf-spectacular template."""
    make_user("docs-render", is_staff=True)
    token = access_token(login(client, "docs-render", "Correct-Horse-42!"))

    response = client.get("/api/v1/docs/", **auth_header(token))

    assert response.status_code == 200
    body = response.content.decode()
    assert "NoReverseMatch" not in body
    assert "{% url" not in body
    assert "{{" not in body
    assert "/api/v1/auth/csrf/" not in body
    assert "accounts:csrf" not in body
    # Stock drf-spectacular template: the Swagger bundle is served and the
    # schema URL is wired, with no project CSRF bootstrap script.
    assert "swagger-ui-bundle.js" in body
    assert "/api/v1/schema/" in body
    assert "schemaAuthNames" in body
    assert "csrfToken" not in body


@pytest.mark.django_db
def test_csrf_bootstrap_endpoint_is_removed(client: Client) -> None:
    """No public CSRF bootstrap route remains."""
    response = client.get("/api/v1/auth/csrf/")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
