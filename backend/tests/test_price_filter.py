"""Regression tests for product price-range filter validation."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import Client

from catalog.models import Category, Product, ProductStore, Store
from tests.conftest import access_token, auth_header, login


@pytest.fixture
def headers(client: Client, administrator) -> dict[str, str]:
    token = access_token(login(client, "administrator", "Correct-Horse-42!"))
    return auth_header(token)


@pytest.fixture
def priced_products(db):
    category = Category.objects.create(name="Price Filter Category")
    store_a = Store.objects.create(name="Price Store A", code="PFA")
    store_b = Store.objects.create(name="Price Store B", code="PFB")
    cheap = Product.objects.create(name="Price Filter Cheap", category=category)
    expensive = Product.objects.create(name="Price Filter Expensive", category=category)
    ProductStore.objects.create(product=cheap, store=store_a, price=Decimal("10.00"), quantity=5)
    ProductStore.objects.create(
        product=expensive, store=store_a, price=Decimal("25.50"), quantity=5
    )
    ProductStore.objects.create(
        product=expensive, store=store_b, price=Decimal("40.00"), quantity=5
    )
    return cheap, expensive, store_a, store_b


@pytest.mark.django_db
def test_min_price_greater_than_max_is_rejected(client: Client, headers, priced_products) -> None:
    store_id = priced_products[2].id
    response = client.get(
        f"/api/v1/products/?store={store_id}&min_price=100&max_price=20", **headers
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["fields"]["min_price"] == ["Minimum price cannot be greater than maximum price."]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query, field",
    [("min_price=-1", "min_price"), ("max_price=-5", "max_price")],
)
def test_negative_price_filters_are_rejected(
    client: Client, headers, priced_products, query, field
) -> None:
    store_id = priced_products[2].id
    response = client.get(f"/api/v1/products/?store={store_id}&{query}", **headers)

    assert response.status_code == 400
    assert response.json()["error"]["fields"][field] == [
        "Price must be greater than or equal to 0."
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("query", ["min_price=abc", "max_price=not-a-number"])
def test_invalid_numeric_price_is_rejected(client: Client, headers, priced_products, query) -> None:
    store_id = priced_products[2].id
    response = client.get(f"/api/v1/products/?store={store_id}&{query}", **headers)

    assert response.status_code == 400
    field = query.split("=")[0]
    assert response.json()["error"]["fields"][field] == ["Please enter a valid price."]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "price_query, expected_names",
    [
        ("min_price=20", ["Price Filter Expensive"]),
        ("max_price=20", ["Price Filter Cheap"]),
        ("min_price=10&max_price=10", ["Price Filter Cheap"]),
        ("min_price=0&max_price=100", ["Price Filter Cheap", "Price Filter Expensive"]),
        ("min_price=10.5&max_price=25.5", ["Price Filter Expensive"]),
    ],
)
def test_valid_price_filters_are_accepted(
    client: Client, headers, priced_products, price_query, expected_names
) -> None:
    # Price filters are store-specific by design; the store parameter is required.
    store_id = priced_products[2].id
    response = client.get(f"/api/v1/products/?store={store_id}&{price_query}", **headers)

    assert response.status_code == 200
    names = [row["name"] for row in response.json()["results"]]
    assert sorted(names) == sorted(expected_names)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    ["min_price=10", "max_price=100", "min_price=10&max_price=100"],
)
def test_price_filter_without_store_returns_validation_error(
    client: Client, headers, priced_products, query
) -> None:
    response = client.get(f"/api/v1/products/?{query}", **headers)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["fields"]["store"] == ["Select a store to filter products by price."]


@pytest.mark.django_db
def test_price_filter_with_invalid_store_returns_validation_error(
    client: Client, headers, priced_products
) -> None:
    response = client.get("/api/v1/products/?store=99999&min_price=10", **headers)

    assert response.status_code == 400
    assert response.json()["error"]["fields"]["store"] == [
        "Select a valid store to filter products by price."
    ]


@pytest.mark.django_db
def test_price_filter_uses_selected_store_price(client: Client, headers, priced_products) -> None:
    store_a = priced_products[2]
    store_b = priced_products[3]

    in_store_a = client.get(f"/api/v1/products/?store={store_a.id}&min_price=30", **headers)
    in_store_b = client.get(f"/api/v1/products/?store={store_b.id}&min_price=30", **headers)

    assert in_store_a.status_code == 200
    assert in_store_b.status_code == 200
    # The expensive product is 25.50 in Store A (excluded) and 40.00 in Store B
    # (included) — proving the filter uses store-specific prices only.
    assert "Price Filter Expensive" not in [r["name"] for r in in_store_a.json()["results"]]
    assert "Price Filter Expensive" in [r["name"] for r in in_store_b.json()["results"]]


@pytest.mark.django_db
def test_store_specific_price_filter_still_works(client: Client, headers, priced_products) -> None:
    _, _, store_a, store_b = priced_products

    in_store_a = client.get(f"/api/v1/products/?store={store_a.id}&min_price=20", **headers)
    in_store_b = client.get(f"/api/v1/products/?store={store_b.id}&min_price=20", **headers)

    assert in_store_a.status_code == 200
    assert in_store_b.status_code == 200
    assert [row["name"] for row in in_store_a.json()["results"]] == ["Price Filter Expensive"]
    assert [row["name"] for row in in_store_b.json()["results"]] == ["Price Filter Expensive"]


@pytest.mark.django_db
def test_search_sort_and_pagination_still_work(client: Client, headers, priced_products) -> None:
    searched = client.get("/api/v1/products/?search=Expensive", **headers)
    assert searched.status_code == 200
    assert [row["name"] for row in searched.json()["results"]] == ["Price Filter Expensive"]

    sorted_results = client.get("/api/v1/products/?ordering=-name", **headers)
    assert sorted_results.status_code == 200
    assert [row["name"] for row in sorted_results.json()["results"]][0] == "Price Filter Expensive"

    paged = client.get("/api/v1/products/?page=1&page_size=1", **headers)
    assert paged.status_code == 200
    assert paged.json()["page_size"] == 1
    assert len(paged.json()["results"]) == 1


@pytest.mark.django_db
def test_price_filter_with_specific_category(client: Client, headers, priced_products) -> None:
    store_id = priced_products[2].id
    category_id = Product.objects.get(name="Price Filter Cheap").category_id

    response = client.get(
        f"/api/v1/products/?store={store_id}&category={category_id}&min_price=20",
        **headers,
    )

    assert response.status_code == 200
    assert [row["name"] for row in response.json()["results"]] == ["Price Filter Expensive"]


@pytest.mark.django_db
def test_combined_search_category_status_and_price_filter(
    client: Client, headers, priced_products
) -> None:
    store_id = priced_products[2].id
    category_id = Product.objects.get(name="Price Filter Expensive").category_id

    response = client.get(
        f"/api/v1/products/?store={store_id}&search=Expensive&category={category_id}"
        "&is_active=true&min_price=20&max_price=30",
        **headers,
    )

    assert response.status_code == 200
    assert [row["name"] for row in response.json()["results"]] == ["Price Filter Expensive"]


@pytest.mark.django_db
def test_price_filter_count_and_pagination_are_accurate(
    client: Client, headers, priced_products
) -> None:
    store_id = priced_products[2].id
    base = f"/api/v1/products/?store={store_id}&min_price=0&max_price=100"

    first = client.get(f"{base}&page=1&page_size=1", **headers)
    second = client.get(f"{base}&page=2&page_size=1", **headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["count"] == 2
    assert second.json()["count"] == 2
    assert first.json()["total_pages"] == 2
    assert len(first.json()["results"]) == 1
    assert len(second.json()["results"]) == 1
    assert first.json()["results"][0]["id"] != second.json()["results"][0]["id"]
