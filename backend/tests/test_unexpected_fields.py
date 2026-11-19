"""Regression tests: catalog write serializers reject unexpected fields."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import Client

from catalog.models import Category, Product, ProductAttribute, ProductImage, ProductStore, Store
from core.serializers import UNEXPECTED_FIELDS_MESSAGE
from tests.conftest import access_token, auth_header, login, post_json


@pytest.fixture
def api(client: Client, administrator):
    return auth_header(access_token(login(client, "administrator", "Correct-Horse-42!")))


@pytest.fixture
def product(db) -> Product:
    return Product.objects.create(
        name="Unexpected Fields Product",
        category=Category.objects.create(name="Unexpected Fields Category"),
    )


def assert_unexpected(response) -> None:
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert body["fields"]["non_field_errors"] == [UNEXPECTED_FIELDS_MESSAGE]
    assert body["request_id"]


@pytest.mark.django_db
def test_category_write_rejects_unexpected_fields(client: Client, api) -> None:
    created = post_json(
        client,
        "/api/v1/categories/",
        {"name": "Strict Category", "unexpected": 1},
        **api,
    )
    assert_unexpected(created)
    assert not Category.objects.filter(name="Strict Category").exists()

    category = Category.objects.create(name="Strict Existing")
    patched = client.patch(
        f"/api/v1/categories/{category.id}/",
        data='{"name":"Renamed","unexpected":1}',
        content_type="application/json",
        **api,
    )
    assert_unexpected(patched)
    category.refresh_from_db()
    assert category.name == "Strict Existing"


@pytest.mark.django_db
def test_store_write_rejects_unexpected_fields(client: Client, api) -> None:
    created = post_json(
        client,
        "/api/v1/stores/",
        {"name": "Strict Store", "code": "STRST", "unexpected": 1},
        **api,
    )
    assert_unexpected(created)
    assert not Store.objects.filter(code="STRST").exists()

    store = Store.objects.create(name="Strict Existing Store", code="STRST2")
    patched = client.patch(
        f"/api/v1/stores/{store.id}/",
        data='{"name":"Renamed","unexpected":1}',
        content_type="application/json",
        **api,
    )
    assert_unexpected(patched)
    store.refresh_from_db()
    assert store.name == "Strict Existing Store"


@pytest.mark.django_db
def test_product_write_rejects_unexpected_and_unauthorized_fields(client: Client, api) -> None:
    category = Category.objects.create(name="Strict Product Category")
    created = post_json(
        client,
        "/api/v1/products/",
        {
            "name": "Strict Product",
            "category_id": category.id,
            "is_superuser": True,
            "slug": "hacked",
        },
        **api,
    )
    assert_unexpected(created)
    assert not Product.objects.filter(name="Strict Product").exists()

    product = Product.objects.create(name="Strict Existing Product", category=category)
    patched = client.patch(
        f"/api/v1/products/{product.id}/",
        data='{"name":"Renamed","permissions":["accounts.manage_users"]}',
        content_type="application/json",
        **api,
    )
    assert_unexpected(patched)
    product.refresh_from_db()
    assert product.name == "Strict Existing Product"


@pytest.mark.django_db
def test_attribute_write_rejects_unexpected_fields(client: Client, api, product) -> None:
    created = post_json(
        client,
        f"/api/v1/products/{product.id}/attributes/",
        {"name": "Brand", "value": "Test", "unexpected": 1},
        **api,
    )
    assert_unexpected(created)
    assert not ProductAttribute.objects.filter(product=product).exists()

    attribute = ProductAttribute.objects.create(product=product, name="Size", value="M")
    patched = client.patch(
        f"/api/v1/products/{product.id}/attributes/{attribute.id}/",
        data='{"value":"L","unexpected":1}',
        content_type="application/json",
        **api,
    )
    assert_unexpected(patched)
    attribute.refresh_from_db()
    assert attribute.value == "M"


@pytest.mark.django_db
def test_image_write_rejects_unexpected_fields(client: Client, api, product) -> None:
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (10, 10), "green").save(buffer, format="PNG")
    upload = SimpleUploadedFile("strict.png", buffer.getvalue(), content_type="image/png")

    created = client.post(
        f"/api/v1/products/{product.id}/images/",
        {"image": upload, "unexpected": "1"},
        **api,
    )
    assert_unexpected(created)
    assert not ProductImage.objects.filter(product=product).exists()

    image = ProductImage.objects.create(product=product, image="products/1/images/strict.png")
    patched = client.patch(
        f"/api/v1/products/{product.id}/images/{image.id}/",
        {"alt_text": "new", "unexpected": "1"},
        content_type="application/x-www-form-urlencoded",
        **api,
    )
    assert_unexpected(patched)
    image.refresh_from_db()
    assert image.alt_text == ""


@pytest.mark.django_db
def test_association_write_rejects_unexpected_fields(client: Client, api, product) -> None:
    store = Store.objects.create(name="Strict Assoc Store", code="STRASSOC")
    created = post_json(
        client,
        f"/api/v1/products/{product.id}/stores/",
        {"store_id": store.id, "price": "10.00", "quantity": 1, "unexpected": 1},
        **api,
    )
    assert_unexpected(created)
    assert not ProductStore.objects.filter(product=product).exists()

    association = ProductStore.objects.create(
        product=product, store=store, price=Decimal("10.00"), quantity=1
    )
    patched = client.patch(
        f"/api/v1/products/{product.id}/stores/{association.id}/",
        data='{"price":"12.00","unexpected":1}',
        content_type="application/json",
        **api,
    )
    assert_unexpected(patched)
    association.refresh_from_db()
    assert association.price == Decimal("10.0000")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method, url, payload",
    [
        ("post", "/api/v1/categories/", {"name": "Valid Category"}),
        ("post", "/api/v1/stores/", {"name": "Valid Store", "code": "VALIDST"}),
    ],
)
def test_valid_post_still_works(client: Client, api, method, url, payload) -> None:
    response = getattr(client, method)(url, data=payload, content_type="application/json", **api)
    assert response.status_code == 201
