"""Query-count regression tests: costs must stay bounded as the catalogue grows."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from catalog.models import Category, Product, ProductImage, ProductStore, Store
from tests.conftest import access_token, auth_header, login


@pytest.fixture
def token(client: Client, administrator) -> str:
    return access_token(login(client, "administrator", "Correct-Horse-42!"))


def seed_catalog(products: int) -> Store:
    """Create a small but realistic catalogue with images and store pricing."""
    category = Category.objects.create(name=f"Category {products}", slug=f"category-{products}")
    store = Store.objects.create(name=f"Store {products}", code=f"S{products}")
    for index in range(products):
        product = Product.objects.create(
            name=f"Product {index:04d}",
            slug=f"product-{products}-{index:04d}",
            category=category,
        )
        ProductImage.objects.create(
            product=product,
            image=f"products/{product.pk}/images/{index}.png",
            is_primary=True,
        )
        ProductStore.objects.create(
            product=product,
            store=store,
            price=Decimal("10.00"),
            quantity=0 if index % 5 == 0 else 10,
        )
    return store


@pytest.mark.parametrize("product_count", [3, 30])
def test_list_endpoint_query_counts_are_bounded(
    db, client: Client, token: str, product_count: int
) -> None:
    store = seed_catalog(product_count)
    product_id = Product.objects.order_by("pk").first().pk
    headers: dict[str, Any] = auth_header(token)
    endpoints = {
        "products": "/api/v1/products/?page=1&page_size=10",
        "products_store_filter": f"/api/v1/products/?page=1&page_size=10&store={store.pk}",
        "product_detail": f"/api/v1/products/{product_id}/",
        "categories": "/api/v1/categories/",
        "stores": "/api/v1/stores/",
        "dashboard": "/api/v1/dashboard/summary/",
        "public_products": "/api/v1/public/products/?page=1&page_size=10",
    }
    # Upper bounds are intentionally generous; the assertion is that they do
    # not grow with product_count, which is what an N+1 would do.
    limits = {
        "products": 12,
        "products_store_filter": 12,
        "product_detail": 14,
        "categories": 8,
        "stores": 8,
        "dashboard": 14,
        "public_products": 8,
    }
    for name, url in endpoints.items():
        with CaptureQueriesContext(connection) as captured:
            response = client.get(url, **headers)
        assert response.status_code == 200, (name, response.status_code)
        assert len(captured.captured_queries) <= limits[name], (
            name,
            product_count,
            len(captured.captured_queries),
        )


def test_dashboard_summary_reports_full_catalogue_totals(db, client: Client, token: str) -> None:
    seed_catalog(12)
    response = client.get("/api/v1/dashboard/summary/", **auth_header(token))
    assert response.status_code == 200
    data = response.json()
    assert data["products"]["total"] == 12
    assert data["stores"] == 1
    availability = data["store_availability"][0]
    assert availability["product_count"] == 12
    # 0, 5, 10 -> three zero-quantity products.
    assert availability["out_of_stock"] == 3
    assert len(data["creation_series"]) == 30


def test_dashboard_out_of_stock_is_independent_of_availability(
    db, client: Client, token: str
) -> None:
    category = Category.objects.create(name="OOS Category", slug="oos-category")
    active_store = Store.objects.create(name="Active Store", code="OOS-A")
    inactive_store = Store.objects.create(name="Inactive Store", code="OOS-I", is_active=False)

    def product(name: str, *, quantity: int, available: bool, store: Store, deleted: bool = False):
        item = Product.objects.create(
            name=name, slug=name.lower().replace(" ", "-"), category=category
        )
        if deleted:
            item.soft_delete()
        ProductStore.objects.create(
            product=item,
            store=store,
            price=Decimal("5.00"),
            quantity=quantity,
            is_available=available,
        )
        return item

    product("Available zero", quantity=0, available=True, store=active_store)
    product("Unavailable zero", quantity=0, available=False, store=active_store)
    product("Available stocked", quantity=5, available=True, store=active_store)
    product("Deleted zero", quantity=0, available=True, store=active_store, deleted=True)
    product("Inactive store zero", quantity=0, available=True, store=inactive_store)

    response = client.get("/api/v1/dashboard/summary/", **auth_header(token))
    assert response.status_code == 200
    by_id = {row["id"]: row for row in response.json()["store_availability"]}
    # Two live zero-quantity products in the active store, independent of the
    # availability flag; the deleted one is excluded.
    assert by_id[active_store.id]["out_of_stock"] == 2
    assert by_id[active_store.id]["product_count"] == 2
    # The inactive store participates in out-of-stock counting as well.
    assert by_id[inactive_store.id]["out_of_stock"] == 1
