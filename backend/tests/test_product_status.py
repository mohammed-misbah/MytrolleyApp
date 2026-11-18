"""Regression tests for product status (is_active) persistence.

These exercise the real PostgreSQL path: create/update over the REST API,
read back through the detail endpoint and the filtered list endpoint, and
verify the stored row. They guard against a form-layer boolean/string mix-up
silently saving the opposite of the submitted status.
"""

from __future__ import annotations

import pytest
from django.test import Client

from catalog.models import Category, Product
from tests.conftest import access_token, auth_header, login, patch_json, post_json


@pytest.fixture
def api_headers(client: Client, administrator) -> dict[str, str]:
    token = access_token(login(client, "administrator", "Correct-Horse-42!"))
    return auth_header(token)


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(name="Status Test Category")


def _create(client: Client, headers: dict[str, str], name: str, category: Category, **extra):
    return post_json(
        client,
        "/api/v1/products/",
        {"name": name, "description": "status regression", "category_id": category.id, **extra},
        **headers,
    )


@pytest.mark.django_db
def test_create_product_with_active_status_persists_true(
    client: Client, api_headers, category
) -> None:
    response = _create(client, api_headers, "Status Active", category, is_active=True)

    assert response.status_code == 201
    assert response.json()["is_active"] is True
    product = Product.objects.get(name="Status Active")
    assert product.is_active is True


@pytest.mark.django_db
def test_create_product_with_inactive_status_persists_false(
    client: Client, api_headers, category
) -> None:
    response = _create(client, api_headers, "Status Inactive", category, is_active=False)

    assert response.status_code == 201
    assert response.json()["is_active"] is False
    product = Product.objects.get(name="Status Inactive")
    assert product.is_active is False


@pytest.mark.django_db
def test_create_product_without_status_defaults_to_active(
    client: Client, api_headers, category
) -> None:
    """The documented serializer default is Active; omitting the field is valid."""
    response = _create(client, api_headers, "Status Default", category)

    assert response.status_code == 201
    assert response.json()["is_active"] is True
    assert Product.objects.get(name="Status Default").is_active is True


@pytest.mark.django_db
def test_patch_status_updates_both_directions(client: Client, api_headers, category) -> None:
    created = _create(client, api_headers, "Status Toggle", category, is_active=False)
    product_id = created.json()["id"]

    activate = patch_json(
        client, f"/api/v1/products/{product_id}/", {"is_active": True}, **api_headers
    )
    assert activate.status_code == 200
    assert activate.json()["is_active"] is True
    assert Product.objects.get(pk=product_id).is_active is True

    deactivate = patch_json(
        client, f"/api/v1/products/{product_id}/", {"is_active": False}, **api_headers
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False


@pytest.mark.django_db
def test_detail_and_list_reflect_persisted_status(client: Client, api_headers, category) -> None:
    active = _create(client, api_headers, "Status Listed Active", category, is_active=True).json()
    inactive = _create(
        client, api_headers, "Status Listed Inactive", category, is_active=False
    ).json()

    detail_active = client.get(f"/api/v1/products/{active['id']}/", **api_headers)
    detail_inactive = client.get(f"/api/v1/products/{inactive['id']}/", **api_headers)
    assert detail_active.json()["is_active"] is True
    assert detail_inactive.json()["is_active"] is False

    active_only = client.get("/api/v1/products/?is_active=true", **api_headers).json()
    inactive_only = client.get("/api/v1/products/?is_active=false", **api_headers).json()
    active_ids = {row["id"] for row in active_only["results"]}
    inactive_ids = {row["id"] for row in inactive_only["results"]}
    assert active["id"] in active_ids
    assert active["id"] not in inactive_ids
    assert inactive["id"] in inactive_ids
    assert inactive["id"] not in active_ids
