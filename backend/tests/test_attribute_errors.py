"""Regression tests for product-attribute validation error responses."""

from __future__ import annotations

import pytest
from django.test import Client

from catalog.models import Category, Product, ProductAttribute
from tests.conftest import access_token, auth_header, login, patch_json, post_json


@pytest.fixture
def headers(client: Client, administrator) -> dict[str, str]:
    token = access_token(login(client, "administrator", "Correct-Horse-42!"))
    return auth_header(token)


@pytest.fixture
def product(db) -> Product:
    category = Category.objects.create(name="Attribute Error Category")
    return Product.objects.create(name="Attribute Error Product", category=category)


@pytest.mark.django_db
def test_duplicate_attribute_returns_specific_field_message(
    client: Client, headers, product
) -> None:
    first = post_json(
        client,
        f"/api/v1/products/{product.id}/attributes/",
        {"name": "Brand", "value": "Logitech"},
        **headers,
    )
    assert first.status_code == 201

    duplicate = post_json(
        client,
        f"/api/v1/products/{product.id}/attributes/",
        {"name": "Brand", "value": "Logitech"},
        **headers,
    )

    assert duplicate.status_code == 400
    error = duplicate.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["fields"]["name"] == [
        "An attribute with the name 'Brand' already exists for this product."
    ]


@pytest.mark.django_db
def test_failed_duplicate_leaves_existing_attribute_unchanged(
    client: Client, headers, product
) -> None:
    original = ProductAttribute.objects.create(product=product, name="Brand", value="Logitech")

    duplicate = post_json(
        client,
        f"/api/v1/products/{product.id}/attributes/",
        {"name": "Brand", "value": "Dell"},
        **headers,
    )

    assert duplicate.status_code == 400
    assert ProductAttribute.objects.count() == 1
    original.refresh_from_db()
    assert original.name == "Brand"
    assert original.value == "Logitech"


@pytest.mark.django_db
def test_valid_attribute_can_still_be_created(client: Client, headers, product) -> None:
    response = post_json(
        client,
        f"/api/v1/products/{product.id}/attributes/",
        {"name": "Size", "value": "27 inch"},
        **headers,
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Size"
    assert ProductAttribute.objects.filter(product=product, name="Size").exists()


@pytest.mark.django_db
def test_required_field_validation_still_works(client: Client, headers, product) -> None:
    empty_name = post_json(
        client,
        f"/api/v1/products/{product.id}/attributes/",
        {"name": "", "value": "Brand value"},
        **headers,
    )
    empty_value = post_json(
        client,
        f"/api/v1/products/{product.id}/attributes/",
        {"name": "Brand", "value": ""},
        **headers,
    )

    assert empty_name.status_code == 400
    assert empty_name.json()["error"]["fields"]["name"]
    assert empty_value.status_code == 400
    assert empty_value.json()["error"]["fields"]["value"]


@pytest.mark.django_db
def test_attribute_edit_and_delete_continue_to_work(client: Client, headers, product) -> None:
    created = post_json(
        client,
        f"/api/v1/products/{product.id}/attributes/",
        {"name": "Brand", "value": "Logitech"},
        **headers,
    ).json()

    updated = patch_json(
        client,
        f"/api/v1/products/{product.id}/attributes/{created['id']}/",
        {"value": "Logitech G"},
        **headers,
    )
    assert updated.status_code == 200
    assert updated.json()["value"] == "Logitech G"

    deleted = client.delete(f"/api/v1/products/{product.id}/attributes/{created['id']}/", **headers)
    assert deleted.status_code == 204
    assert not ProductAttribute.objects.filter(pk=created["id"]).exists()


@pytest.mark.django_db
def test_database_unique_constraint_still_enforced(client: Client, headers, product) -> None:
    """Application validation and the DB constraint both reject duplicates."""
    from django.db import IntegrityError, transaction

    ProductAttribute.objects.create(product=product, name="Brand", value="Logitech")
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductAttribute.objects.create(product=product, name="Brand", value="Dell")
