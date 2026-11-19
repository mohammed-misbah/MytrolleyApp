"""Regression tests for constant query count in the product listing endpoint."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from catalog.models import Category, Product, ProductAttribute, ProductImage, ProductStore, Store
from tests.conftest import access_token, auth_header, login


def _seed(product_count: int) -> tuple[Category, Store]:
    category = Category.objects.create(name=f"Query Category {product_count}")
    store = Store.objects.create(name=f"Query Store {product_count}", code=f"QS{product_count}")
    for index in range(product_count):
        product = Product.objects.create(name=f"Query Product {index}", category=category)
        ProductAttribute.objects.create(product=product, name="Brand", value="Test")
        ProductImage.objects.create(product=product, image=f"products/1/images/{index}.jpg")
        ProductStore.objects.create(
            product=product, store=store, price=Decimal("10.00"), quantity=1
        )
    return category, store


def _count_queries(client: Client, headers: dict[str, str], url: str) -> int:
    with CaptureQueriesContext(connection) as captured:
        response = client.get(url, **headers)
    assert response.status_code == 200
    return len(captured)


@pytest.mark.django_db
def test_product_list_query_count_is_constant(client: Client, administrator) -> None:
    """Listing 1, 5 and 10 products must use the same number of SQL queries."""
    token = access_token(login(client, "administrator", "Correct-Horse-42!"))
    headers = auth_header(token)
    counts = []
    for size in (1, 5, 10):
        _seed(size)
        counts.append(_count_queries(client, headers, "/api/v1/products/?page_size=10"))
    assert len(set(counts)) == 1, f"query counts by product count: {counts}"


@pytest.mark.django_db
def test_product_list_single_count_query(client: Client, administrator) -> None:
    """The duplicated filter/sort block must not produce two COUNT queries."""
    _seed(3)
    token = access_token(login(client, "administrator", "Correct-Horse-42!"))
    headers = auth_header(token)
    with CaptureQueriesContext(connection) as captured:
        response = client.get("/api/v1/products/?page_size=10", **headers)
    assert response.status_code == 200
    count_queries = [
        q for q in captured.captured_queries if q["sql"].lstrip().startswith("SELECT COUNT")
    ]
    assert len(count_queries) == 1, f"count queries: {len(count_queries)}"
