"""Permanent regression tests for database uniqueness and index cleanup."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier, Lock

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client

from catalog.models import Category, Product, ProductAttribute, ProductStore, Store
from tests.conftest import access_token, auth_header, login, post_json

User = get_user_model()


@pytest.mark.django_db
def test_category_name_unique_case_insensitively_at_database_level() -> None:
    Category.objects.create(name="Case Category")
    with pytest.raises(IntegrityError), transaction.atomic():
        Category.objects.create(name="CASE CATEGORY")
    # Direct SQL bypasses model/serializer validation but not the database.
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO catalog_category "
            "(name, slug, description, is_active, created_at, updated_at) "
            "VALUES ('case category', 'case-category-2', '', true, NOW(), NOW())"
        )


@pytest.mark.django_db
def test_attribute_name_unique_per_product_case_insensitively() -> None:
    product = Product.objects.create(
        name="Attribute Product", category=Category.objects.create(name="Attr Category")
    )
    other = Product.objects.create(
        name="Other Product", category=Category.objects.get(name="Attr Category")
    )
    ProductAttribute.objects.create(product=product, name="Brand", value="A")
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductAttribute.objects.create(product=product, name="BRAND", value="B")
    # The same name on another product is allowed.
    ProductAttribute.objects.create(product=other, name="brand", value="C")
    assert ProductAttribute.objects.count() == 2


@pytest.mark.django_db
def test_store_code_unique_including_direct_database_writes() -> None:
    Store.objects.create(name="Code Store", code="ABC")
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO catalog_store "
            "(name, code, description, address, is_active, created_at, updated_at) "
            "VALUES ('Code Store 2', 'abc', '', '', true, NOW(), NOW())"
        )
    assert Store.objects.count() == 1


@pytest.mark.django_db
def test_redundant_indexes_removed_and_constraints_preserved() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename IN "
            "('catalog_category','catalog_product','catalog_store','catalog_productattribute')"
        )
        indexes = {row[0] for row in cursor.fetchall()}
    for redundant in ("product_slug_idx", "store_code_idx", "product_attr_name_idx"):
        assert redundant not in indexes
    for required in (
        "catalog_product_slug_key",
        "catalog_store_code_key",
        "unique_product_attribute_name",
        "category_name_ci_unique",
        "store_code_ci_unique",
        "product_attribute_name_ci_unique",
    ):
        assert required in indexes


@pytest.mark.django_db
def test_duplicate_conflicts_return_structured_errors(client: Client, administrator) -> None:
    token = access_token(login(client, "administrator", "Correct-Horse-42!"))
    headers = auth_header(token)
    category = Category.objects.create(name="Conflict Category")
    product = Product.objects.create(name="Conflict Product", category=category)
    ProductAttribute.objects.create(product=product, name="Brand", value="A")
    store = Store.objects.create(name="Conflict Store", code="CONFST")
    ProductStore.objects.create(product=product, store=store, price=Decimal("1"), quantity=1)

    cases = (
        ("/api/v1/categories/", {"name": "conflict category"}, 400, "name", None),
        ("/api/v1/stores/", {"name": "Other", "code": "confst"}, 400, "code", None),
        (
            f"/api/v1/products/{product.id}/attributes/",
            {"name": "brand", "value": "B"},
            400,
            "name",
            None,
        ),
        (
            f"/api/v1/products/{product.id}/stores/",
            {"store_id": store.id, "price": "2", "quantity": 1},
            409,
            None,
            "This product is already associated with the selected store.",
        ),
    )
    counts_before = (
        Category.objects.count(),
        Store.objects.count(),
        ProductAttribute.objects.count(),
        ProductStore.objects.count(),
    )
    for url, payload, expected_status, field, message in cases:
        response = post_json(client, url, payload, **headers)
        assert response.status_code == expected_status, response.content.decode()
        body = response.json()["error"]
        assert body["code"] == ("CONFLICT" if expected_status == 409 else "VALIDATION_ERROR")
        if field:
            assert body["fields"][field]
        if message:
            assert body["message"] == message
        assert body["request_id"]
    counts_after = (
        Category.objects.count(),
        Store.objects.count(),
        ProductAttribute.objects.count(),
        ProductStore.objects.count(),
    )
    assert counts_after == counts_before


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_category_names_create_single_row(administrator) -> None:
    barrier = Barrier(2)
    statuses: list[int] = []
    lock = Lock()

    def worker(name: str) -> None:
        close_old_connections()
        worker_client = Client()
        token = access_token(login(worker_client, "administrator", "Correct-Horse-42!"))
        try:
            barrier.wait(timeout=10)
            response = post_json(
                worker_client,
                "/api/v1/categories/",
                {"name": name},
                **auth_header(token),
            )
            with lock:
                statuses.append(response.status_code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, name) for name in ("Concurrent Cat", "CONCURRENT CAT")]
        for future in futures:
            future.result(timeout=30)

    # The loser may be rejected by serializer validation (400) or by the
    # database uniqueness constraint (409); both are safe outcomes.
    assert sorted(statuses) in ([201, 400], [201, 409])
    assert Category.objects.filter(name__iexact="Concurrent Cat").count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_attributes_create_single_row(administrator) -> None:
    category = Category.objects.create(name="Concurrent Attr Category")
    product = Product.objects.create(name="Concurrent Attr Product", category=category)
    barrier = Barrier(2)
    statuses: list[int] = []
    lock = Lock()

    def worker() -> None:
        close_old_connections()
        worker_client = Client()
        token = access_token(login(worker_client, "administrator", "Correct-Horse-42!"))
        try:
            barrier.wait(timeout=10)
            response = post_json(
                worker_client,
                f"/api/v1/products/{product.id}/attributes/",
                {"name": "Brand", "value": "x"},
                **auth_header(token),
            )
            with lock:
                statuses.append(response.status_code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        for future in futures:
            future.result(timeout=30)

    # The loser may be rejected by serializer validation (400) or by the
    # database uniqueness constraint (409); both are safe outcomes.
    assert sorted(statuses) in ([201, 400], [201, 409])
    assert ProductAttribute.objects.filter(product=product).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_associations_create_single_row(administrator) -> None:
    category = Category.objects.create(name="Concurrent Assoc Category")
    product = Product.objects.create(name="Concurrent Assoc Product", category=category)
    store = Store.objects.create(name="Concurrent Assoc Store", code="CASST")
    barrier = Barrier(2)
    statuses: list[int] = []
    lock = Lock()

    def worker() -> None:
        close_old_connections()
        worker_client = Client()
        token = access_token(login(worker_client, "administrator", "Correct-Horse-42!"))
        try:
            barrier.wait(timeout=10)
            response = post_json(
                worker_client,
                f"/api/v1/products/{product.id}/stores/",
                {"store_id": store.id, "price": "5.00", "quantity": 1},
                **auth_header(token),
            )
            with lock:
                statuses.append(response.status_code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        for future in futures:
            future.result(timeout=30)

    # The loser may be rejected by serializer validation (400) or by the
    # database uniqueness constraint (409); both are safe outcomes.
    assert sorted(statuses) in ([201, 400], [201, 409])
    assert ProductStore.objects.filter(product=product, store=store).count() == 1
