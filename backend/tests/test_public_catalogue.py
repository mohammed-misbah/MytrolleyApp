"""Regression tests for the anonymous, read-only public product catalogue."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from PIL import Image

from catalog.models import Category, Product, ProductAttribute, ProductImage, ProductStore, Store
from tests.conftest import access_token, auth_header, login, make_user, patch_json

PUBLIC = "/api/v1/public/"


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(name="Public Category")


@pytest.fixture
def store(db) -> Store:
    return Store.objects.create(name="Public Store", code="PUBST")


@pytest.fixture
def product(db, category, store) -> Product:
    item = Product.objects.create(name="Public Product", category=category)
    ProductStore.objects.create(
        product=item, store=store, price=Decimal("10.0000"), quantity=12, is_available=True
    )
    return item


def _list(client: Client, url: str = "products/", **params):
    return client.get(PUBLIC + url, params or None)


def _detail(client: Client, product_id: int):
    return client.get(f"{PUBLIC}products/{product_id}/")


# --- 1-4: anonymous read access -------------------------------------------


@pytest.mark.django_db
def test_anonymous_can_list_active_stores(client: Client, store) -> None:
    response = client.get(PUBLIC + "stores/")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [store.id]


@pytest.mark.django_db
def test_anonymous_can_list_active_categories(client: Client, category) -> None:
    response = client.get(PUBLIC + "categories/")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [category.id]


@pytest.mark.django_db
def test_anonymous_can_list_products(client: Client, product) -> None:
    response = _list(client)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["id"] == product.id


@pytest.mark.django_db
def test_anonymous_can_read_product_details(client: Client, product) -> None:
    ProductAttribute.objects.create(product=product, name="Brand", value="Acme")
    response = _detail(client, product.id)
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Public Product"
    assert body["attributes"] == [
        {"id": ProductAttribute.objects.get(product=product).id, "name": "Brand", "value": "Acme"}
    ]
    assert body["stores"][0]["price"] == "10.0000"


# --- 5-11, 26: visibility rules -------------------------------------------


@pytest.mark.django_db
def test_inactive_stores_are_excluded_everywhere(client: Client, category) -> None:
    hidden = Store.objects.create(name="Hidden Store", code="HIDST", is_active=False)
    visible = Store.objects.create(name="Visible Store", code="VIST")
    item = Product.objects.create(name="Only Hidden", category=category)
    ProductStore.objects.create(product=item, store=hidden, price=Decimal("1"), quantity=1)

    assert hidden.id not in [row["id"] for row in client.get(PUBLIC + "stores/").json()]
    assert _list(client).json()["count"] == 0
    assert _detail(client, item.id).status_code == 404

    # A product with one visible and one hidden association remains public,
    # but the hidden store never appears in nested data or price searches.
    ProductStore.objects.create(product=item, store=visible, price=Decimal("2"), quantity=2)
    assert [row["store"]["id"] for row in _detail(client, item.id).json()["stores"]] == [visible.id]
    assert not Store.objects.filter(pk=hidden.id, is_active=True).exists()


@pytest.mark.django_db
def test_inactive_categories_and_inactive_ancestors_are_excluded(client: Client, store) -> None:
    hidden = Category.objects.create(name="Hidden Category", is_active=False)
    visible = Category.objects.create(name="Visible Category")
    child_of_hidden = Category.objects.create(name="Child Of Hidden", parent=hidden)
    item = Product.objects.create(name="In Hidden Category", category=hidden)
    ProductStore.objects.create(product=item, store=store, price=Decimal("1"), quantity=1)
    child_item = Product.objects.create(name="In Hidden Ancestor", category=child_of_hidden)
    ProductStore.objects.create(product=child_item, store=store, price=Decimal("1"), quantity=1)
    visible_item = Product.objects.create(name="In Visible Category", category=visible)
    ProductStore.objects.create(product=visible_item, store=store, price=Decimal("1"), quantity=1)

    category_ids = {row["id"] for row in client.get(PUBLIC + "categories/").json()}
    assert hidden.id not in category_ids
    assert child_of_hidden.id not in category_ids
    assert visible.id in category_ids
    result_ids = {row["id"] for row in _list(client).json()["results"]}
    assert item.id not in result_ids
    assert child_item.id not in result_ids
    assert visible_item.id in result_ids
    assert _detail(client, item.id).status_code == 404
    assert _detail(client, child_item.id).status_code == 404


@pytest.mark.django_db
def test_inactive_and_soft_deleted_products_are_excluded(client: Client, category, store) -> None:
    inactive = Product.objects.create(name="Inactive", category=category, is_active=False)
    deleted = Product.objects.create(name="Deleted", category=category)
    deleted.soft_delete()
    for item in (inactive, deleted):
        ProductStore.objects.create(product=item, store=store, price=Decimal("1"), quantity=1)

    body = _list(client).json()
    assert body["count"] == 0
    assert _detail(client, inactive.id).status_code == 404
    assert _detail(client, deleted.id).status_code == 404


@pytest.mark.django_db
def test_unavailable_associations_are_excluded(client: Client, category, store) -> None:
    item = Product.objects.create(name="Unavailable", category=category)
    ProductStore.objects.create(
        product=item, store=store, price=Decimal("1"), quantity=1, is_available=False
    )
    assert _list(client).json()["count"] == 0
    assert _detail(client, item.id).status_code == 404


@pytest.mark.django_db
def test_visibility_parameters_cannot_bypass_rules(client: Client, product) -> None:
    for params in ({"is_active": "false"}, {"is_available": "false"}, {"deleted_at": "x"}):
        response = _list(client, **params)
        assert response.status_code == 400, response.content.decode()
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    # The product remains visible with normal parameters.
    assert _list(client).json()["count"] == 1


# --- 12-15: independent store pricing -------------------------------------


@pytest.mark.django_db
def test_store_a_and_store_b_return_their_own_prices_and_quantities(
    client: Client, product, category
) -> None:
    store_b = Store.objects.create(name="Store B", code="STOREB")
    ProductStore.objects.create(
        product=product, store=store_b, price=Decimal("20.0000"), quantity=200
    )
    store_a_id = ProductStore.objects.get(product=product, store__code="PUBST").store_id

    first = _list(client, store=store_a_id).json()
    second = _list(client, store=store_b.id).json()
    assert first["count"] == 1
    assert second["count"] == 1
    first_row = first["results"][0]
    second_row = second["results"][0]
    assert first_row["selected_store_price"]["price"] == "10.0000"
    assert first_row["selected_store_price"]["quantity"] == 12
    assert second_row["selected_store_price"]["price"] == "20.0000"
    assert second_row["selected_store_price"]["quantity"] == 200

    first_detail = client.get(f"{PUBLIC}products/{product.id}/?store={store_a_id}").json()
    second_detail = client.get(f"{PUBLIC}products/{product.id}/?store={store_b.id}").json()
    assert first_detail["selected_store"]["store"]["id"] == store_a_id
    assert second_detail["selected_store"]["store"]["id"] == store_b.id
    # Alternative eligible stores remain inspectable in both detail responses.
    assert {row["store"]["id"] for row in first_detail["stores"]} == {store_a_id, store_b.id}
    assert first_detail["selected_store"]["price"] == "10.0000"
    assert second_detail["selected_store"]["price"] == "20.0000"


@pytest.mark.django_db
def test_price_filtering_and_ordering_use_selected_store(client: Client, product, category) -> None:
    store_b = Store.objects.create(name="Store B", code="STOREB")
    other = Product.objects.create(name="Other Product", category=category)
    ProductStore.objects.create(
        product=product, store=store_b, price=Decimal("20.0000"), quantity=1
    )
    ProductStore.objects.create(product=other, store=store_b, price=Decimal("5.0000"), quantity=1)
    store_b_id = store_b.id

    within = _list(client, store=store_b_id, min_price="15", max_price="25").json()
    assert {row["id"] for row in within["results"]} == {product.id}
    assert within["results"][0]["selected_store_price"]["price"] == "20.0000"

    ordered = _list(client, store=store_b_id, ordering="price").json()
    assert [row["id"] for row in ordered["results"]] == [other.id, product.id]


# --- 16-19: search, filters, pagination, validation ------------------------


@pytest.mark.django_db
def test_search_category_filter_and_pagination(client: Client, product, category, store) -> None:
    for index in range(3):
        item = Product.objects.create(
            name=f"Coffee Blend {index}", description="Aromatic", category=category
        )
        ProductStore.objects.create(product=item, store=store, price=Decimal("3"), quantity=1)

    found = _list(client, search="aromatic").json()
    assert found["count"] == 3
    assert _list(client, search="COFFEE").json()["count"] == 3

    by_category = _list(client, category=category.id).json()
    assert by_category["count"] == 4

    first = _list(client, page=1, page_size=2).json()
    second = _list(client, page=2, page_size=2).json()
    assert first["count"] == 4
    assert first["total_pages"] == 2
    assert first["page"] == 1
    assert first["page_size"] == 2
    assert len(first["results"]) == 2
    assert len(second["results"]) == 2
    assert not {row["id"] for row in first["results"]} & {row["id"] for row in second["results"]}


@pytest.mark.django_db
def test_invalid_query_parameters_return_validation_errors(client: Client, product) -> None:
    cases = (
        {"page": 0},
        {"page_size": 101},
        {"store": 999999},
        {"ordering": "price"},
        {"min_price": "20", "max_price": "10", "store": 1},
        {"search": "x", "page": "not-a-number"},
    )
    for params in cases:
        response = _list(client, **params)
        assert response.status_code == 400, params
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    invalid_detail = client.get(f"{PUBLIC}products/{product.id}/?store=abc")
    assert invalid_detail.status_code == 400


# --- 20-23: read-only and administrative security --------------------------


@pytest.mark.django_db
def test_public_endpoints_reject_all_write_methods(client: Client, product) -> None:
    urls = (
        PUBLIC + "stores/",
        PUBLIC + "categories/",
        PUBLIC + "products/",
        f"{PUBLIC}products/{product.id}/",
    )
    payload = {"name": "Tampered", "code": "TAMPER", "price": "999"}
    before = (
        Store.objects.count(),
        Category.objects.count(),
        Product.objects.count(),
        product.name,
    )
    for url in urls:
        for method in (client.post, client.put, client.patch, client.delete):
            response = method(url, data=payload, content_type="application/json")
            assert response.status_code == 405, (method, url, response.status_code)
    after = (
        Store.objects.count(),
        Category.objects.count(),
        Product.objects.count(),
        Product.objects.get(pk=product.pk).name,
    )
    assert after == before
    assert ProductStore.objects.get(product=product).price == Decimal("10.0000")


@pytest.mark.django_db
def test_admin_endpoints_still_require_authentication(client: Client, product) -> None:
    for url in (
        "/api/v1/stores/",
        "/api/v1/categories/",
        "/api/v1/products/",
        f"/api/v1/products/{product.id}/",
    ):
        assert client.get(url).status_code == 401


@pytest.mark.django_db
def test_authenticated_without_business_permission_is_still_blocked(
    client: Client, roles, product
) -> None:
    make_user("public-reader")
    headers = auth_header(access_token(login(client, "public-reader", "Correct-Horse-42!")))
    assert client.get("/api/v1/products/", **headers).status_code == 403
    assert (
        patch_json(
            client, f"/api/v1/products/{product.id}/", {"name": "Nope"}, **headers
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_authorized_admin_operations_still_work(client: Client, administrator, product) -> None:
    headers = auth_header(access_token(login(client, "administrator", "Correct-Horse-42!")))
    assert client.get("/api/v1/products/", **headers).status_code == 200
    response = patch_json(
        client, f"/api/v1/products/{product.id}/", {"name": "Admin Edited"}, **headers
    )
    assert response.status_code == 200
    product.refresh_from_db()
    assert product.name == "Admin Edited"


# --- 24-25: image URLs and counts -----------------------------------------


@pytest.mark.django_db
def test_public_image_url_is_absolute_and_image_is_served(
    client: Client, product, tmp_path
) -> None:
    buffer = BytesIO()
    Image.new("RGB", (12, 12), "blue").save(buffer, format="PNG")
    upload = SimpleUploadedFile("public.png", buffer.getvalue(), content_type="image/png")
    with override_settings(MEDIA_ROOT=tmp_path):
        image = ProductImage.objects.create(product=product, image=upload, is_primary=True)
        body = _list(client).json()
        image_url = body["results"][0]["primary_image"]["image_url"]
        assert image_url.startswith("http://")
        assert "/api/v1/public/images/" in image_url
        assert str(image.id) in image_url
        assert "\\" not in image_url
        response = client.get(image_url.replace("http://testserver", ""))
        assert response.status_code == 200
        assert response["Content-Type"].startswith("image/")
        assert b"PNG" in b"".join(response.streaming_content)
        ProductImage.objects.filter(pk=image.pk).delete()


@pytest.mark.django_db
def test_public_counts_exclude_non_public_records(client: Client, category, store) -> None:
    visible = Product.objects.create(name="Counted", category=category)
    ProductStore.objects.create(product=visible, store=store, price=Decimal("1"), quantity=1)
    inactive = Product.objects.create(name="Not Counted", category=category, is_active=False)
    ProductStore.objects.create(product=inactive, store=store, price=Decimal("1"), quantity=1)
    deleted = Product.objects.create(name="Deleted", category=category)
    deleted.soft_delete()
    ProductStore.objects.create(product=deleted, store=store, price=Decimal("1"), quantity=1)
    hidden_store = Store.objects.create(name="Hidden", code="HIDCNT", is_active=False)
    ProductStore.objects.create(product=visible, store=hidden_store, price=Decimal("1"), quantity=1)

    stores = {row["id"]: row for row in client.get(PUBLIC + "stores/").json()}
    categories = {row["id"]: row for row in client.get(PUBLIC + "categories/").json()}
    assert stores[store.id]["product_count"] == 1
    assert categories[category.id]["product_count"] == 1
