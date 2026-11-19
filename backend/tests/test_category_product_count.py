"""Regression tests for the Categories page product count."""

from __future__ import annotations

import pytest
from django.test import Client

from catalog.models import Category, Product
from tests.conftest import access_token, auth_header, login, patch_json, post_json


@pytest.fixture
def headers(client: Client, administrator) -> dict[str, str]:
    token = access_token(login(client, "administrator", "Correct-Horse-42!"))
    return auth_header(token)


@pytest.fixture
def categories(db) -> tuple[Category, Category]:
    return Category.objects.create(name="Count Category A"), Category.objects.create(
        name="Count Category B"
    )


def count_for(client: Client, headers: dict[str, str], category_id: int) -> int:
    response = client.get(f"/api/v1/categories/{category_id}/", **headers)
    assert response.status_code == 200
    return response.json()["product_count"]


@pytest.mark.django_db
def test_count_starts_at_zero(client: Client, headers, categories) -> None:
    assert count_for(client, headers, categories[0].id) == 0


@pytest.mark.django_db
def test_count_includes_active_and_inactive_products(client: Client, headers, categories) -> None:
    category = categories[0]
    active = post_json(
        client,
        "/api/v1/products/",
        {"name": "Count Active", "category_id": category.id},
        **headers,
    ).json()
    inactive = post_json(
        client,
        "/api/v1/products/",
        {"name": "Count Inactive", "category_id": category.id, "is_active": False},
        **headers,
    ).json()

    assert active["is_active"] is True
    assert inactive["is_active"] is False
    assert count_for(client, headers, category.id) == 2


@pytest.mark.django_db
def test_deactivation_and_reactivation_do_not_change_count(
    client: Client, headers, categories
) -> None:
    category = categories[0]
    created = post_json(
        client,
        "/api/v1/products/",
        {"name": "Count Toggle", "category_id": category.id},
        **headers,
    ).json()

    patch_json(
        client,
        f"/api/v1/products/{created['id']}/",
        {"is_active": False},
        **headers,
    )
    assert count_for(client, headers, category.id) == 1

    patch_json(
        client,
        f"/api/v1/products/{created['id']}/",
        {"is_active": True},
        **headers,
    )
    assert count_for(client, headers, category.id) == 1


@pytest.mark.django_db
def test_delete_endpoint_excludes_product_from_count(client: Client, headers, categories) -> None:
    """Soft deletion removes a product from category counts but keeps its row."""
    category = categories[0]
    created = post_json(
        client,
        "/api/v1/products/",
        {"name": "Count Deleted", "category_id": category.id},
        **headers,
    ).json()

    assert count_for(client, headers, category.id) == 1
    response = client.delete(f"/api/v1/products/{created['id']}/", **headers)
    assert response.status_code == 204
    deleted = Product.all_objects.get(pk=created["id"])
    assert deleted.deleted_at is not None
    assert count_for(client, headers, category.id) == 0


@pytest.mark.django_db
def test_removed_product_row_is_excluded_from_count(client: Client, headers, categories) -> None:
    category = categories[0]
    product = Product.objects.create(name="Count Removed", category=category)
    assert count_for(client, headers, category.id) == 1

    Product.objects.filter(pk=product.pk).delete()
    assert count_for(client, headers, category.id) == 0


@pytest.mark.django_db
def test_category_reassignment_updates_both_counts(client: Client, headers, categories) -> None:
    first, second = categories
    created = post_json(
        client,
        "/api/v1/products/",
        {"name": "Count Moved", "category_id": first.id},
        **headers,
    ).json()
    assert count_for(client, headers, first.id) == 1
    assert count_for(client, headers, second.id) == 0

    patch_json(
        client,
        f"/api/v1/products/{created['id']}/",
        {"category_id": second.id},
        **headers,
    )
    assert count_for(client, headers, first.id) == 0
    assert count_for(client, headers, second.id) == 1


@pytest.mark.django_db
def test_category_deletion_protection_still_applies_with_inactive_product(
    client: Client, headers, categories
) -> None:
    category = categories[0]
    Product.objects.create(name="Count Protected", category=category, is_active=False)

    response = client.delete(f"/api/v1/categories/{category.id}/", **headers)

    assert response.status_code == 409
    assert Category.objects.filter(pk=category.pk).exists()
