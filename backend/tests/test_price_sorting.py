"""Regression tests for store-specific product price sorting."""

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
    category = Category.objects.create(name="Price Sort Category")
    store_a = Store.objects.create(name="Sort Store A", code="SORTA")
    store_b = Store.objects.create(name="Sort Store B", code="SORTB")
    alpha = Product.objects.create(name="Sort Alpha", category=category)
    beta = Product.objects.create(name="Sort Beta", category=category)
    # Prices are deliberately reversed between stores to prove sorting is
    # store-specific and never based on a global product price.
    ProductStore.objects.create(product=alpha, store=store_a, price=Decimal("30.00"), quantity=5)
    ProductStore.objects.create(product=beta, store=store_a, price=Decimal("10.00"), quantity=5)
    ProductStore.objects.create(product=alpha, store=store_b, price=Decimal("5.00"), quantity=5)
    ProductStore.objects.create(product=beta, store=store_b, price=Decimal("50.00"), quantity=5)
    return alpha, beta, store_a, store_b


@pytest.mark.django_db
@pytest.mark.parametrize("ordering", ["price", "-price"])
def test_price_sorting_without_store_returns_validation_error(
    client: Client, headers, priced_products, ordering
) -> None:
    response = client.get(f"/api/v1/products/?ordering={ordering}", **headers)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["fields"]["ordering"] == ["Select a store to sort products by price."]


@pytest.mark.django_db
def test_price_sorting_with_invalid_store_returns_validation_error(
    client: Client, headers, priced_products
) -> None:
    response = client.get("/api/v1/products/?store=99999&ordering=price", **headers)

    assert response.status_code == 400
    assert response.json()["error"]["fields"]["store"] == [
        "Select a valid store to sort products by price."
    ]


@pytest.mark.django_db
def test_ascending_price_sorting_uses_selected_store(
    client: Client, headers, priced_products
) -> None:
    _, _, store_a, store_b = priced_products

    in_a = client.get(f"/api/v1/products/?store={store_a.id}&ordering=price", **headers)
    in_b = client.get(f"/api/v1/products/?store={store_b.id}&ordering=price", **headers)

    assert in_a.status_code == 200
    assert in_b.status_code == 200
    assert [row["name"] for row in in_a.json()["results"]] == ["Sort Beta", "Sort Alpha"]
    assert [row["name"] for row in in_b.json()["results"]] == ["Sort Alpha", "Sort Beta"]


@pytest.mark.django_db
def test_descending_price_sorting_uses_selected_store(
    client: Client, headers, priced_products
) -> None:
    _, _, store_a, _ = priced_products

    response = client.get(f"/api/v1/products/?store={store_a.id}&ordering=-price", **headers)

    assert response.status_code == 200
    assert [row["name"] for row in response.json()["results"]] == ["Sort Alpha", "Sort Beta"]


@pytest.mark.django_db
def test_search_and_pagination_still_work_with_price_sorting(
    client: Client, headers, priced_products
) -> None:
    _, _, store_a, _ = priced_products

    response = client.get(
        f"/api/v1/products/?store={store_a.id}&ordering=price&search=Sort&page=1&page_size=1",
        **headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert data["page_size"] == 1
    assert [row["name"] for row in data["results"]] == ["Sort Beta"]
