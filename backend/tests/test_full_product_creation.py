"""Atomic full-product creation endpoint tests."""

from __future__ import annotations

import json
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image
from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductAttribute, ProductImage, ProductStore, Store
from tests.conftest import access_token, login, make_user

URL = "/api/v1/products/create-with-relations/"


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(name="Full Create Category", slug="full-create-category")


@pytest.fixture
def stores(db) -> list[Store]:
    return [
        Store.objects.create(name="Full Create Store A", code="FCSA"),
        Store.objects.create(name="Full Create Store B", code="FCSB"),
    ]


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (4, 4), "green").save(buffer, format="PNG")
    return buffer.getvalue()


def payload(category_id: int, store_ids: list[int], **overrides) -> dict:
    data = {
        "name": "Complete Product",
        "description": "Created in one submission",
        "category_id": category_id,
        "is_active": True,
        "attributes": json.dumps([{"name": "Brand", "value": "MyTrolley"}]),
        "stores": json.dumps(
            [
                {"store_id": store_ids[0], "price": "12.50", "quantity": 7, "is_available": True},
                {
                    "store_id": store_ids[1],
                    "price": "19.99",
                    "quantity": 0,
                    "is_available": False,
                },
            ]
        ),
    }
    data.update(overrides)
    return data


def api_for(client: Client) -> APIClient:
    make_user("creator", role="Administrator", is_staff=True)
    token = access_token(login(client, "creator", "Correct-Horse-42!"))
    api = APIClient(enforce_csrf_checks=True)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api


def post(api: APIClient, data: dict, images: list | None = None):
    body = dict(data)
    if images is not None:
        body["images"] = images
    return api.post(URL, body, format="multipart")


def images(count: int) -> list[SimpleUploadedFile]:
    return [
        SimpleUploadedFile(f"image{index}.png", png_bytes(), content_type="image/png")
        for index in range(count)
    ]


def test_creates_product_with_all_relations_atomically(
    db, client: Client, category, stores
) -> None:
    api = api_for(client)
    ids = [store.id for store in stores]
    data = payload(
        category.id,
        ids,
        attributes=json.dumps(
            [{"name": "Brand", "value": "MyTrolley"}, {"name": "Size", "value": "M"}]
        ),
    )

    response = post(api, data, images(2))

    assert response.status_code == 201, response.content[:500]
    product = Product.objects.get(pk=response.json()["id"])
    assert product.name == "Complete Product"
    assert product.category_id == category.id
    assert product.attributes.count() == 2
    assert product.images.count() == 2
    assert product.store_associations.count() == 2
    assert product.images.filter(is_primary=True).count() == 1
    associations = {a.store_id: a for a in product.store_associations.all()}
    assert float(associations[ids[0]].price) == 12.50
    assert associations[ids[0]].quantity == 7
    assert associations[ids[1]].quantity == 0
    assert associations[ids[1]].is_available is False


def test_invalid_nested_data_rolls_back_everything(db, client: Client, category, stores) -> None:
    api = api_for(client)
    ids = [store.id for store in stores]
    data = payload(
        category.id,
        ids,
        stores=json.dumps(
            [{"store_id": ids[0], "price": "-1", "quantity": 2, "is_available": True}]
        ),
    )

    response = post(api, data, images(1))

    assert response.status_code == 400
    assert Product.objects.count() == 0
    assert ProductImage.objects.count() == 0
    assert ProductAttribute.objects.count() == 0
    assert ProductStore.objects.count() == 0


def test_duplicate_store_is_rejected(db, client: Client, category, stores) -> None:
    api = api_for(client)
    store_id = stores[0].id
    data = payload(
        category.id,
        [store_id, store_id],
        stores=json.dumps(
            [{"store_id": store_id, "price": "5", "quantity": 1, "is_available": True}] * 2
        ),
    )
    response = post(api, data)
    assert response.status_code == 400
    assert any("stores[1]" in key for key in response.json()["error"]["fields"])
    assert Product.objects.count() == 0


def test_duplicate_attribute_is_rejected(db, client: Client, category, stores) -> None:
    api = api_for(client)
    data = payload(
        category.id,
        [store.id for store in stores],
        attributes=json.dumps([{"name": "Brand", "value": "A"}, {"name": "brand", "value": "B"}]),
    )
    response = post(api, data)
    assert response.status_code == 400
    assert Product.objects.count() == 0


def test_too_many_images_or_large_image_are_rejected(db, client: Client, category, stores) -> None:
    api = api_for(client)
    ids = [store.id for store in stores]

    response = post(api, payload(category.id, ids), images(11))
    assert response.status_code == 400
    assert Product.objects.count() == 0

    large = SimpleUploadedFile(
        "large.png", b"\x89PNG\r\n\x1a\n" + b"0" * 1_048_576, content_type="image/png"
    )
    response = post(api, payload(category.id, ids), [large])
    assert response.status_code == 400
    assert Product.objects.count() == 0


def test_invalid_category_is_rejected(db, client: Client, category, stores) -> None:
    api = api_for(client)
    response = post(api, payload(999_999, [store.id for store in stores]))
    assert response.status_code == 400
    assert Product.objects.count() == 0
