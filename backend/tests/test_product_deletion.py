"""Regression tests for product soft deletion.

Deactivation (``is_active``) and deletion (``deleted_at``) are separate
operations. A deleted product stays in the database with all related rows,
but disappears from every normal catalogue query and endpoint.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from PIL import Image

from catalog.models import Category, Product, ProductAttribute, ProductImage, ProductStore, Store
from tests.conftest import access_token, auth_header, login, make_user, patch_json, post_json


@pytest.fixture
def api_headers(client: Client, administrator) -> dict[str, str]:
    return auth_header(access_token(login(client, "administrator", "Correct-Horse-42!")))


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(name="Deletion Test Category")


def _headers(client: Client, username: str) -> dict[str, str]:
    return auth_header(access_token(login(client, username, "Correct-Horse-42!")))


def _product(name: str, category: Category, **extra) -> Product:
    return Product.objects.create(name=name, category=category, **extra)


# --- Authorization ---------------------------------------------------------


@pytest.mark.django_db
def test_administrator_can_delete_product(client: Client, api_headers, category) -> None:
    product = _product("Admin Delete", category)
    response = client.delete(f"/api/v1/products/{product.id}/", **api_headers)
    assert response.status_code == 204
    assert Product.all_objects.get(pk=product.id).deleted_at is not None


@pytest.mark.django_db
def test_data_entry_can_delete_product(client: Client, data_entry, category) -> None:
    headers = _headers(client, "dataentry")
    product = _product("Data Entry Delete", category)
    response = client.delete(f"/api/v1/products/{product.id}/", **headers)
    assert response.status_code == 204
    assert Product.all_objects.get(pk=product.id).deleted_at is not None


@pytest.mark.django_db
def test_unauthorized_user_cannot_delete_product(client: Client, roles, category) -> None:
    make_user("catalog-reader")
    headers = _headers(client, "catalog-reader")
    product = _product("Unauthorized Delete", category)
    response = client.delete(f"/api/v1/products/{product.id}/", **headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert Product.all_objects.get(pk=product.id).deleted_at is None


@pytest.mark.django_db
def test_anonymous_user_cannot_delete_product(client: Client, category) -> None:
    product = _product("Anonymous Delete", category)
    response = client.delete(f"/api/v1/products/{product.id}/")
    assert response.status_code == 401
    assert Product.all_objects.get(pk=product.id).deleted_at is None


# --- Deletion semantics ----------------------------------------------------


@pytest.mark.django_db
def test_active_and_inactive_products_can_be_deleted(client: Client, api_headers, category) -> None:
    active = _product("Active Delete", category)
    inactive = _product("Inactive Delete", category, is_active=False)

    for product in (active, inactive):
        assert client.delete(f"/api/v1/products/{product.id}/", **api_headers).status_code == 204

    active_after = Product.all_objects.get(pk=active.id)
    inactive_after = Product.all_objects.get(pk=inactive.id)
    assert active_after.deleted_at is not None and active_after.is_active is True
    assert inactive_after.deleted_at is not None and inactive_after.is_active is False


@pytest.mark.django_db
def test_deleted_record_remains_in_database(client: Client, api_headers, category) -> None:
    product = _product("Retained Row", category)
    client.delete(f"/api/v1/products/{product.id}/", **api_headers)
    assert Product.objects.count() == 0
    assert Product.all_objects.count() == 1
    assert Product.all_objects.get(pk=product.id).name == "Retained Row"


@pytest.mark.django_db
def test_deletion_is_transaction_safe(client: Client, api_headers, category, monkeypatch) -> None:
    product = _product("Atomic Delete", category)

    def failing_soft_delete(instance: Product) -> None:
        Product.all_objects.filter(pk=instance.pk).update(deleted_at=timezone.now())
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(Product, "soft_delete", failing_soft_delete)
    response = client.delete(f"/api/v1/products/{product.id}/", **api_headers)
    assert response.status_code == 500
    # The UPDATE was rolled back with the surrounding transaction.
    assert Product.all_objects.get(pk=product.id).deleted_at is None


@pytest.mark.django_db
def test_repeated_deletion_returns_404(client: Client, api_headers, category) -> None:
    product = _product("Delete Twice", category)
    assert client.delete(f"/api/v1/products/{product.id}/", **api_headers).status_code == 204
    response = client.delete(f"/api/v1/products/{product.id}/", **api_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- Exclusion from catalogue queries --------------------------------------


@pytest.mark.django_db
def test_deleted_product_excluded_from_list_and_status_filters(
    client: Client, api_headers, category
) -> None:
    active = _product("Filter Active", category)
    inactive = _product("Filter Inactive", category, is_active=False)
    deleted = _product("Filter Deleted", category)
    client.delete(f"/api/v1/products/{deleted.id}/", **api_headers)

    def ids(url: str) -> set[int]:
        response = client.get(url, **api_headers)
        assert response.status_code == 200
        return {row["id"] for row in response.json()["results"]}

    assert ids("/api/v1/products/") == {active.id, inactive.id}
    assert ids("/api/v1/products/?is_active=true") == {active.id}
    assert ids("/api/v1/products/?is_active=false") == {inactive.id}
    for url in (
        "/api/v1/products/?search=Filter",
        "/api/v1/products/?ordering=-name",
        "/api/v1/products/?ordering=created_at",
    ):
        assert deleted.id not in ids(url)


@pytest.mark.django_db
def test_deleted_product_excluded_from_active_catalogue_and_counts(
    client: Client, api_headers, category
) -> None:
    active = _product("Catalogue Active", category)
    deleted = _product("Catalogue Deleted", category)
    client.delete(f"/api/v1/products/{deleted.id}/", **api_headers)

    response = client.get("/api/v1/products/?is_active=true&page_size=1", **api_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert {row["id"] for row in body["results"]} == {active.id}

    # Dashboard totals come from the same unfiltered list count.
    all_count = client.get("/api/v1/products/?page_size=1", **api_headers).json()["count"]
    assert all_count == 1


@pytest.mark.django_db
def test_deleted_product_excluded_from_store_and_price_queries(
    client: Client, api_headers, category
) -> None:
    store = Store.objects.create(name="Delete Store", code="DELST")
    kept = _product("Store Kept", category)
    deleted = _product("Store Deleted", category)
    for product in (kept, deleted):
        ProductStore.objects.create(product=product, store=store, price=Decimal("10"), quantity=1)
    client.delete(f"/api/v1/products/{deleted.id}/", **api_headers)

    by_store = client.get(f"/api/v1/products/?store={store.id}", **api_headers).json()
    assert {row["id"] for row in by_store["results"]} == {kept.id}
    sorted_by_price = client.get(
        f"/api/v1/products/?store={store.id}&ordering=price", **api_headers
    ).json()
    assert {row["id"] for row in sorted_by_price["results"]} == {kept.id}


# --- No access through normal endpoints ------------------------------------


@pytest.mark.django_db
def test_deleted_product_cannot_be_retrieved_or_updated(
    client: Client, api_headers, category
) -> None:
    product = _product("No Access", category)
    client.delete(f"/api/v1/products/{product.id}/", **api_headers)

    assert client.get(f"/api/v1/products/{product.id}/", **api_headers).status_code == 404
    assert (
        patch_json(
            client, f"/api/v1/products/{product.id}/", {"name": "Renamed"}, **api_headers
        ).status_code
        == 404
    )
    # Reactivating through the normal status update is not possible.
    reactivate = patch_json(
        client, f"/api/v1/products/{product.id}/", {"is_active": True}, **api_headers
    )
    assert reactivate.status_code == 404
    assert Product.all_objects.get(pk=product.id).is_active is True


@pytest.mark.django_db
def test_deleted_product_cannot_receive_child_resources(
    client: Client, api_headers, category
) -> None:
    product = _product("No Children", category)
    client.delete(f"/api/v1/products/{product.id}/", **api_headers)

    buffer = BytesIO()
    Image.new("RGB", (5, 5), "red").save(buffer, format="PNG")
    upload = SimpleUploadedFile("deleted.png", buffer.getvalue(), content_type="image/png")

    responses = [
        client.get(f"/api/v1/products/{product.id}/attributes/", **api_headers),
        post_json(
            client,
            f"/api/v1/products/{product.id}/attributes/",
            {"name": "Brand", "value": "Test"},
            **api_headers,
        ),
        client.get(f"/api/v1/products/{product.id}/images/", **api_headers),
        client.post(f"/api/v1/products/{product.id}/images/", {"image": upload}, **api_headers),
        client.get(f"/api/v1/products/{product.id}/stores/", **api_headers),
        post_json(
            client,
            f"/api/v1/products/{product.id}/stores/",
            {
                "store_id": Store.objects.create(name="Child Store", code="CHST").id,
                "price": "5.00",
                "quantity": 1,
            },
            **api_headers,
        ),
    ]
    for response in responses:
        assert response.status_code == 404, response.content.decode()


# --- Inactive products are unaffected --------------------------------------


@pytest.mark.django_db
def test_inactive_product_remains_visible_and_reactivatable(
    client: Client, api_headers, category
) -> None:
    product = _product("Stay Inactive", category, is_active=False)
    listed = client.get("/api/v1/products/?is_active=false", **api_headers).json()
    assert product.id in {row["id"] for row in listed["results"]}

    response = patch_json(
        client, f"/api/v1/products/{product.id}/", {"is_active": True}, **api_headers
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is True
    refreshed = Product.all_objects.get(pk=product.id)
    assert refreshed.deleted_at is None
    assert refreshed.is_active is True


# --- Related data and integrity --------------------------------------------


@pytest.mark.django_db
def test_related_data_and_parent_records_are_retained(
    client: Client, api_headers, category
) -> None:
    store = Store.objects.create(name="Retain Store", code="RETST")
    product = _product("Retain Relations", category)
    ProductAttribute.objects.create(product=product, name="Brand", value="Acme")
    ProductImage.objects.create(product=product, image="products/1/images/keep.jpg")
    ProductStore.objects.create(product=product, store=store, price=Decimal("12.50"), quantity=7)

    assert client.delete(f"/api/v1/products/{product.id}/", **api_headers).status_code == 204

    assert ProductAttribute.objects.filter(product=product).count() == 1
    assert ProductAttribute.objects.get(product=product).value == "Acme"
    assert ProductImage.objects.filter(product=product).count() == 1
    association = ProductStore.objects.get(product=product, store=store)
    assert association.price == Decimal("12.5000")
    assert association.quantity == 7
    assert Category.objects.filter(pk=category.pk).exists()
    assert Store.objects.filter(pk=store.pk).exists()


@pytest.mark.django_db
def test_category_and_store_deletion_protection_keeps_soft_deleted_relations(
    client: Client, api_headers, category
) -> None:
    store = Store.objects.create(name="Protect Store", code="PROST")
    product = _product("Protected Relation", category)
    ProductStore.objects.create(product=product, store=store, price=Decimal("1"), quantity=1)
    client.delete(f"/api/v1/products/{product.id}/", **api_headers)

    category_response = client.delete(f"/api/v1/categories/{category.id}/", **api_headers)
    store_response = client.delete(f"/api/v1/stores/{store.id}/", **api_headers)
    assert category_response.status_code == 409
    assert store_response.status_code == 409
    assert Category.objects.filter(pk=category.pk).exists()
    assert Store.objects.filter(pk=store.pk).exists()


@pytest.mark.django_db
def test_new_product_can_reuse_name_of_deleted_product(
    client: Client, api_headers, category
) -> None:
    first = _product("Reused Name", category)
    assert first.slug == "reused-name"
    client.delete(f"/api/v1/products/{first.id}/", **api_headers)

    created = post_json(
        client,
        "/api/v1/products/",
        {"name": "Reused Name", "category_id": category.id},
        **api_headers,
    )
    assert created.status_code == 201, created.content.decode()
    assert created.json()["slug"] == "reused-name-1"
    assert Product.objects.filter(name="Reused Name").count() == 1


@pytest.mark.django_db
def test_counts_exclude_deleted_products(client: Client, api_headers, category) -> None:
    store = Store.objects.create(name="Count Store", code="CNTST")
    kept = _product("Count Kept", category)
    deleted = _product("Count Deleted", category)
    ProductStore.objects.create(product=kept, store=store, price=Decimal("1"), quantity=1)
    ProductStore.objects.create(product=deleted, store=store, price=Decimal("1"), quantity=1)

    def category_count() -> int:
        response = client.get(f"/api/v1/categories/{category.id}/", **api_headers)
        return response.json()["product_count"]

    def store_count() -> int:
        return client.get(f"/api/v1/stores/{store.id}/", **api_headers).json()["product_count"]

    assert category_count() == 2
    assert store_count() == 2

    client.delete(f"/api/v1/products/{deleted.id}/", **api_headers)

    assert category_count() == 1
    assert store_count() == 1


@pytest.mark.django_db
def test_pagination_remains_accurate_after_deletion(client: Client, api_headers, category) -> None:
    products = [_product(f"Page Product {i}", category) for i in range(3)]
    first_page = client.get("/api/v1/products/?page_size=2", **api_headers).json()
    assert first_page["count"] == 3
    assert first_page["total_pages"] == 2

    client.delete(f"/api/v1/products/{products[0].id}/", **api_headers)
    remaining = client.get("/api/v1/products/?page_size=2", **api_headers).json()
    assert remaining["count"] == 2
    assert remaining["total_pages"] == 1
    assert len(remaining["results"]) == 2
    assert products[0].id not in {row["id"] for row in remaining["results"]}
    assert client.get("/api/v1/products/?page=2&page_size=2", **api_headers).json()["results"] == []


@pytest.mark.django_db
def test_strict_validation_and_query_optimization_still_work(
    client: Client, api_headers, category
) -> None:
    from core.serializers import UNEXPECTED_FIELDS_MESSAGE

    unexpected = post_json(
        client,
        "/api/v1/products/",
        {"name": "Strict", "category_id": category.id, "is_superuser": True},
        **api_headers,
    )
    assert unexpected.status_code == 400
    assert unexpected.json()["error"]["fields"]["non_field_errors"] == [UNEXPECTED_FIELDS_MESSAGE]

    store = Store.objects.create(name="Query Store", code="QST")
    for index in range(3):
        product = _product(f"Query Product {index}", category)
        ProductImage.objects.create(product=product, image=f"products/1/images/{index}.jpg")
        ProductStore.objects.create(product=product, store=store, price=Decimal("1"), quantity=1)
    doomed = _product("Query Doomed", category)
    doomed.deleted_at = timezone.now()
    doomed.save()
    with CaptureQueriesContext(connection) as captured:
        response = client.get("/api/v1/products/?page_size=10", **api_headers)
    assert response.status_code == 200
    assert doomed.id not in {row["id"] for row in response.json()["results"]}
    count_queries = [
        query
        for query in captured.captured_queries
        if query["sql"].lstrip().startswith("SELECT COUNT")
    ]
    assert len(count_queries) == 1
