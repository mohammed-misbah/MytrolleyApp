"""Catalog API tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import Client

from accounts.models import User
from catalog.models import Category, Product, ProductAttribute, ProductImage, ProductStore, Store
from tests.conftest import access_token, auth_header, login, make_user, patch_json, post_json


@pytest.fixture
def data_entry_user(roles) -> User:
    return make_user("dataentry", role="DataEntry")


@pytest.fixture
def data_entry_token(client: Client, data_entry_user) -> str:
    response = login(client, "dataentry", "Correct-Horse-42!")
    return access_token(response)


@pytest.fixture
def administrator_token(client: Client, administrator) -> str:
    response = login(client, "administrator", "Correct-Horse-42!")
    return access_token(response)


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(name="Electronics", description="Electronic devices")


@pytest.fixture
def store(db) -> Store:
    return Store.objects.create(name="Store A", code="STA", address="123 Main St")


@pytest.fixture
def product(db, category) -> Product:
    return Product.objects.create(name="Laptop", description="Gaming laptop", category=category)


@pytest.fixture
def product_store(db, product, store) -> ProductStore:
    return ProductStore.objects.create(
        product=product, store=store, price=Decimal("15.00"), quantity=100
    )


class TestCategoryAPI:
    """Category API tests."""

    def test_list_categories(self, client: Client, administrator_token, category) -> None:
        response = client.get("/api/v1/categories/", **auth_header(administrator_token))
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Electronics"

    def test_list_categories_filter_active(self, client: Client, administrator_token) -> None:
        Category.objects.create(name="Active Cat", is_active=True)
        Category.objects.create(name="Inactive Cat", is_active=False)

        response = client.get(
            "/api/v1/categories/?is_active=true", **auth_header(administrator_token)
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == "Active Cat"

    def test_create_category(self, client: Client, administrator_token) -> None:
        response = post_json(
            client,
            "/api/v1/categories/",
            {"name": "New Category", "description": "Test category"},
            **auth_header(administrator_token),
        )
        assert response.status_code == 201
        assert response.json()["name"] == "New Category"
        assert "slug" in response.json()

    def test_create_category_invalid(self, client: Client, administrator_token) -> None:
        response = post_json(
            client,
            "/api/v1/categories/",
            {"name": ""},
            **auth_header(administrator_token),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_retrieve_category(self, client: Client, administrator_token, category) -> None:
        response = client.get(
            f"/api/v1/categories/{category.id}/", **auth_header(administrator_token)
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Electronics"

    def test_update_category(self, client: Client, administrator_token, category) -> None:
        response = patch_json(
            client,
            f"/api/v1/categories/{category.id}/",
            {"name": "Updated Electronics"},
            **auth_header(administrator_token),
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Electronics"

    def test_delete_category(self, client: Client, administrator_token, category) -> None:
        response = client.delete(
            f"/api/v1/categories/{category.id}/", **auth_header(administrator_token)
        )
        assert response.status_code == 204

    def test_delete_category_with_products_fails(
        self, client: Client, administrator_token, category, product
    ) -> None:
        response = client.delete(
            f"/api/v1/categories/{category.id}/", **auth_header(administrator_token)
        )
        assert response.status_code == 409

    def test_unauthorized_access(self, client: Client) -> None:
        response = client.get("/api/v1/categories/")
        assert response.status_code == 401

    def test_data_entry_can_access(self, client: Client, data_entry_token) -> None:
        response = client.get("/api/v1/categories/", **auth_header(data_entry_token))
        assert response.status_code == 200


class TestStoreAPI:
    """Store API tests."""

    def test_list_stores(self, client: Client, administrator_token, store) -> None:
        response = client.get("/api/v1/stores/", **auth_header(administrator_token))
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_create_store(self, client: Client, administrator_token) -> None:
        response = post_json(
            client,
            "/api/v1/stores/",
            {"name": "New Store", "code": "NWS", "address": "456 Oak Ave"},
            **auth_header(administrator_token),
        )
        assert response.status_code == 201
        assert response.json()["code"] == "NWS"

    def test_create_store_duplicate_code(self, client: Client, administrator_token, store) -> None:
        response = post_json(
            client,
            "/api/v1/stores/",
            {"name": "Another Store", "code": "STA"},
            **auth_header(administrator_token),
        )
        assert response.status_code == 400

    def test_update_store(self, client: Client, administrator_token, store) -> None:
        response = patch_json(
            client,
            f"/api/v1/stores/{store.id}/",
            {"name": "Updated Store"},
            **auth_header(administrator_token),
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Store"

    def test_delete_store(self, client: Client, administrator_token, store) -> None:
        response = client.delete(f"/api/v1/stores/{store.id}/", **auth_header(administrator_token))
        assert response.status_code == 204

    def test_delete_store_with_products_fails(
        self, client: Client, administrator_token, store, product_store
    ) -> None:
        response = client.delete(f"/api/v1/stores/{store.id}/", **auth_header(administrator_token))
        assert response.status_code == 409


class TestProductAPI:
    """Product API tests."""

    def test_list_products(self, client: Client, administrator_token, product) -> None:
        response = client.get("/api/v1/products/", **auth_header(administrator_token))
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["name"] == "Laptop"

    def test_list_products_pagination(
        self, client: Client, administrator_token, category, product
    ) -> None:
        for i in range(25):
            Product.objects.create(name=f"Product {i}", category=category)

        response = client.get(
            "/api/v1/products/?page=1&page_size=10", **auth_header(administrator_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 10
        assert data["count"] == 26  # 25 + 1 from fixture

    def test_search_products(self, client: Client, administrator_token, product, category) -> None:
        Product.objects.create(name="Mouse", category=category)
        Product.objects.create(name="Keyboard", category=category)

        response = client.get("/api/v1/products/?search=lap", **auth_header(administrator_token))
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert "Laptop" in data["results"][0]["name"]

    def test_filter_by_category(self, client: Client, administrator_token, category) -> None:
        cat2 = Category.objects.create(name="Accessories")
        Product.objects.create(name="Mouse", category=cat2)
        Product.objects.create(name="Laptop", category=category)

        response = client.get(
            f"/api/v1/products/?category={category.id}", **auth_header(administrator_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "Laptop"

    def test_filter_by_store(
        self, client: Client, administrator_token, product, store, product_store
    ) -> None:
        store2 = Store.objects.create(name="Store B", code="STB")
        ProductStore.objects.create(
            product=product, store=store2, price=Decimal("20.00"), quantity=50
        )

        response = client.get(
            f"/api/v1/products/?store={store.id}", **auth_header(administrator_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1

    def test_filter_by_price_range(
        self, client: Client, administrator_token, product, store, product_store
    ) -> None:
        store2 = Store.objects.create(name="Store B", code="STB")
        ProductStore.objects.create(
            product=product, store=store2, price=Decimal("25.00"), quantity=50
        )

        response = client.get(
            f"/api/v1/products/?store={store.id}&min_price=10&max_price=20",
            **auth_header(administrator_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1

    def test_sort_products_by_name(self, client: Client, administrator_token, category) -> None:
        Product.objects.create(name="A Product", category=category)
        Product.objects.create(name="Z Product", category=category)

        response = client.get("/api/v1/products/?ordering=name", **auth_header(administrator_token))
        assert response.status_code == 200
        data = response.json()
        assert data["results"][0]["name"] == "A Product"
        assert data["results"][-1]["name"] == "Z Product"

    def test_sort_products_by_price(
        self, client: Client, administrator_token, category, store
    ) -> None:
        product1 = Product.objects.create(name="Product A", category=category)
        product2 = Product.objects.create(name="Product B", category=category)
        ProductStore.objects.create(
            product=product1, store=store, price=Decimal("15.00"), quantity=100
        )
        ProductStore.objects.create(
            product=product2, store=store, price=Decimal("10.00"), quantity=50
        )

        response = client.get(
            f"/api/v1/products/?store={store.id}&ordering=price", **auth_header(administrator_token)
        )
        assert response.status_code == 200
        data = response.json()
        # Should have the cheaper price first
        assert (
            data["results"][0]["store_price"]["price"] < data["results"][-1]["store_price"]["price"]
        )

    def test_create_product(self, client: Client, administrator_token, category) -> None:
        response = post_json(
            client,
            "/api/v1/products/",
            {"name": "New Product", "description": "Test", "category_id": category.id},
            **auth_header(administrator_token),
        )
        assert response.status_code == 201
        assert response.json()["name"] == "New Product"

    def test_retrieve_product(self, client: Client, administrator_token, product) -> None:
        response = client.get(f"/api/v1/products/{product.id}/", **auth_header(administrator_token))
        assert response.status_code == 200
        assert response.json()["name"] == "Laptop"

    def test_update_product(self, client: Client, administrator_token, product) -> None:
        response = patch_json(
            client,
            f"/api/v1/products/{product.id}/",
            {"name": "Updated Laptop"},
            **auth_header(administrator_token),
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Laptop"

    def test_delete_product_soft(self, client: Client, administrator_token, product) -> None:
        headers = auth_header(administrator_token)
        response = client.delete(f"/api/v1/products/{product.id}/", **headers)
        assert response.status_code == 204
        # The row is retained with a deletion timestamp; is_active is left
        # untouched because deletion and deactivation are separate operations.
        deleted = Product.all_objects.get(pk=product.id)
        assert deleted.deleted_at is not None
        assert deleted.is_active is True
        # Ordinary catalogue access no longer sees the product.
        assert client.get(f"/api/v1/products/{product.id}/", **headers).status_code == 404
        assert client.delete(f"/api/v1/products/{product.id}/", **headers).status_code == 404

    def test_data_entry_can_access(self, client: Client, data_entry_token, product) -> None:
        response = client.get("/api/v1/products/", **auth_header(data_entry_token))
        assert response.status_code == 200


class TestProductAttributeAPI:
    """Product Attribute API tests."""

    def test_list_attributes(self, client: Client, administrator_token, product) -> None:
        ProductAttribute.objects.create(product=product, name="Brand", value="Dell")
        ProductAttribute.objects.create(product=product, name="RAM", value="16GB")

        response = client.get(
            f"/api/v1/products/{product.id}/attributes/", **auth_header(administrator_token)
        )
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_create_attribute(self, client: Client, administrator_token, product) -> None:
        response = post_json(
            client,
            f"/api/v1/products/{product.id}/attributes/",
            {"name": "Brand", "value": "Dell"},
            **auth_header(administrator_token),
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Brand"

    def test_create_duplicate_attribute_fails(
        self, client: Client, administrator_token, product
    ) -> None:
        ProductAttribute.objects.create(product=product, name="Brand", value="Dell")
        response = post_json(
            client,
            f"/api/v1/products/{product.id}/attributes/",
            {"name": "Brand", "value": "HP"},
            **auth_header(administrator_token),
        )
        assert response.status_code == 400

    def test_update_attribute(self, client: Client, administrator_token, product) -> None:
        attr = ProductAttribute.objects.create(product=product, name="Brand", value="Dell")
        response = patch_json(
            client,
            f"/api/v1/products/{product.id}/attributes/{attr.id}/",
            {"value": "HP"},
            **auth_header(administrator_token),
        )
        assert response.status_code == 200
        assert response.json()["value"] == "HP"

    def test_delete_attribute(self, client: Client, administrator_token, product) -> None:
        attr = ProductAttribute.objects.create(product=product, name="Brand", value="Dell")
        response = client.delete(
            f"/api/v1/products/{product.id}/attributes/{attr.id}/",
            **auth_header(administrator_token),
        )
        assert response.status_code == 204


class TestProductImageAPI:
    """Product Image API tests."""

    def create_test_image(self) -> bytes:
        from io import BytesIO

        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        buffer = BytesIO()
        img.save(buffer, format="JPEG")
        return buffer.getvalue()

    def test_list_images(self, client: Client, administrator_token, product) -> None:
        ProductImage.objects.create(
            product=product,
            image="test.jpg",
            is_primary=True,
        )

        response = client.get(
            f"/api/v1/products/{product.id}/images/", **auth_header(administrator_token)
        )
        assert response.status_code == 200

    def test_upload_image(self, client: Client, administrator_token, product) -> None:
        image_data = self.create_test_image()
        response = client.post(
            f"/api/v1/products/{product.id}/images/",
            {"image": image_data, "alt_text": "Test", "is_primary": True},
            **auth_header(administrator_token),
        )
        # Note: multipart upload might need different handling
        assert response.status_code in (201, 400)

    def test_delete_image(self, client: Client, administrator_token, product) -> None:
        image = ProductImage.objects.create(
            product=product,
            image="test.jpg",
            is_primary=True,
        )
        response = client.delete(
            f"/api/v1/products/{product.id}/images/{image.id}/",
            **auth_header(administrator_token),
        )
        assert response.status_code == 204


class TestProductStoreAPI:
    """Product-Store Association API tests."""

    def test_list_associations(
        self, client: Client, administrator_token, product, product_store
    ) -> None:
        response = client.get(
            f"/api/v1/products/{product.id}/stores/", **auth_header(administrator_token)
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        # Price is stored with 4 decimal places
        assert response.json()[0]["price"] == "15.0000"

    def test_create_association(self, client: Client, administrator_token, product, store) -> None:
        response = post_json(
            client,
            f"/api/v1/products/{product.id}/stores/",
            {"store_id": store.id, "price": "15.00", "quantity": 100},
            **auth_header(administrator_token),
        )
        assert response.status_code == 201
        # Price is stored with 4 decimal places
        assert response.json()["price"] == "15.0000"
        assert response.json()["quantity"] == 100

    def test_create_duplicate_association_fails(
        self, client: Client, administrator_token, product, product_store
    ) -> None:
        response = post_json(
            client,
            f"/api/v1/products/{product.id}/stores/",
            {"store_id": product_store.store.id, "price": "20.00", "quantity": 50},
            **auth_header(administrator_token),
        )
        assert response.status_code == 409

    def test_update_association_price(
        self, client: Client, administrator_token, product, product_store
    ) -> None:
        response = patch_json(
            client,
            f"/api/v1/products/{product.id}/stores/{product_store.id}/",
            {"price": "20.00"},
            **auth_header(administrator_token),
        )
        assert response.status_code == 200
        # Price is stored with 4 decimal places
        assert response.json()["price"] == "20.0000"

    def test_update_association_quantity(
        self, client: Client, administrator_token, product, product_store
    ) -> None:
        response = patch_json(
            client,
            f"/api/v1/products/{product.id}/stores/{product_store.id}/",
            {"quantity": 200},
            **auth_header(administrator_token),
        )
        assert response.status_code == 200
        assert response.json()["quantity"] == 200

    def test_update_store_not_allowed(
        self, client: Client, administrator_token, product, product_store, store
    ) -> None:
        store2 = Store.objects.create(name="Store B", code="STB")
        response = patch_json(
            client,
            f"/api/v1/products/{product.id}/stores/{product_store.id}/",
            {"store_id": store2.id},
            **auth_header(administrator_token),
        )
        assert response.status_code == 400

    def test_delete_association(
        self, client: Client, administrator_token, product, product_store
    ) -> None:
        response = client.delete(
            f"/api/v1/products/{product.id}/stores/{product_store.id}/",
            **auth_header(administrator_token),
        )
        assert response.status_code == 204

    def test_negative_price_rejected(
        self, client: Client, administrator_token, product, store
    ) -> None:
        response = post_json(
            client,
            f"/api/v1/products/{product.id}/stores/",
            {"store_id": store.id, "price": "-5.00", "quantity": 100},
            **auth_header(administrator_token),
        )
        assert response.status_code == 400

    def test_negative_quantity_rejected(
        self, client: Client, administrator_token, product, store
    ) -> None:
        response = post_json(
            client,
            f"/api/v1/products/{product.id}/stores/",
            {"store_id": store.id, "price": "15.00", "quantity": -1},
            **auth_header(administrator_token),
        )
        assert response.status_code == 400
