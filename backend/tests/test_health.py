"""Liveness/readiness behaviour and database-failure handling."""

from __future__ import annotations

from unittest import mock

import pytest
from django.db import OperationalError
from django.test import Client

from core.health import database_is_ready


@pytest.mark.django_db
def test_liveness_does_not_require_database(client: Client, django_assert_num_queries) -> None:
    with django_assert_num_queries(0):
        response = client.get("/api/v1/health/live/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "postgres" not in response.content.decode().lower()
    assert "no-store" in response["Cache-Control"]


@pytest.mark.django_db
def test_readiness_executes_database_query(client: Client, django_assert_max_num_queries) -> None:
    with django_assert_max_num_queries(4):
        response = client.get("/api/v1/health/ready/")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert "no-store" in response["Cache-Control"]


@pytest.mark.django_db
def test_readiness_returns_generic_503_when_database_unavailable(
    client: Client,
    caplog,
) -> None:
    with mock.patch("core.views.database_is_ready", return_value=False):
        response = client.get("/api/v1/health/ready/")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "no-store" in response["Cache-Control"]
    text = response.content.decode().lower()
    for detail in ("postgres", "connection", "password", "host", "traceback"):
        assert detail not in text


@pytest.mark.django_db
def test_database_helper_swallows_database_error_details(caplog) -> None:
    error = OperationalError(
        'connection failed: password authentication failed for user "secret-user"'
    )
    with mock.patch("core.health.connections") as mocked_connections:
        mocked_connections.__getitem__.return_value.cursor.side_effect = error
        assert database_is_ready() is False

    assert "health.ready.database_unavailable" in caplog.text
    assert "secret-user" not in caplog.text
    assert "password" not in caplog.text


@pytest.mark.django_db
def test_liveness_is_independent_of_database(client: Client) -> None:
    with mock.patch("core.views.database_is_ready", side_effect=AssertionError):
        response = client.get("/api/v1/health/live/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoints_are_public() -> None:
    from core.views import LivenessView, ReadinessView

    assert LivenessView.permission_classes[0].__name__ == "AllowAny"
    assert ReadinessView.permission_classes[0].__name__ == "AllowAny"
