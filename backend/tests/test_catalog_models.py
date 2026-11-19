"""Catalog model tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.db.models import ProtectedError
from PIL import Image

from catalog.models import Category, Product, ProductAttribute, ProductImage, ProductStore, Store


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


@pytest.mark.django_db
class TestCategoryModel:
    """Category model tests."""

    def test_create_category(self) -> None:
        category = Category.objects.create(name="Electronics", description="Electronic devices")
        assert category.name == "Electronics"
        assert category.slug == "electronics"
        assert category.is_active is True

    def test_category_slug_auto_generation(self) -> None:
        category = Category.objects.create(name="Grocery & Food")
        assert category.slug == "grocery-food"

    def test_category_slug_uniqueness(self) -> None:
        # Distinct names that slugify identically verify slug disambiguation;
        # case-only variants are now rejected by the case-insensitive name
        # constraint (covered in test_database_constraints.py).
        Category.objects.create(name="Electronics")
        category2 = Category.objects.create(name="Electronics!")
        assert category2.slug == "electronics-1"

    def test_category_parent_relationship(self) -> None:
        parent = Category.objects.create(name="Electronics")
        child = Category.objects.create(name="Laptops", parent=parent)
        assert child.parent == parent
        assert parent.children.first() == child

    def test_category_parent_protect_on_delete(self) -> None:
        parent = Category.objects.create(name="Electronics")
        Category.objects.create(name="Laptops", parent=parent)
        with pytest.raises(ProtectedError):
            parent.delete()

    def test_category_str(self) -> None:
        category = Category.objects.create(name="Electronics")
        assert str(category) == "Electronics"

    def test_category_full_path(self) -> None:
        parent = Category.objects.create(name="Electronics")
        child = Category.objects.create(name="Laptops", parent=parent)
        grandchild = Category.objects.create(name="Gaming", parent=child)
        assert parent.full_path == "Electronics"
        assert child.full_path == "Electronics > Laptops"
        assert grandchild.full_path == "Electronics > Laptops > Gaming"

    def test_category_inactive_filter(self) -> None:
        Category.objects.create(name="Active Cat", is_active=True)
        Category.objects.create(name="Inactive Cat", is_active=False)
        assert Category.objects.filter(is_active=True).count() == 1
        assert Category.objects.filter(is_active=False).count() == 1


@pytest.mark.django_db
class TestStoreModel:
    """Store model tests."""

    def test_create_store(self) -> None:
        store = Store.objects.create(name="Store A", code="STA", address="123 Main St")
        assert store.name == "Store A"
        assert store.code == "STA"
        assert store.is_active is True

    def test_store_code_uniqueness(self) -> None:
        Store.objects.create(name="Store A", code="STA")
        with pytest.raises(IntegrityError):
            Store.objects.create(name="Store B", code="STA")

    def test_store_code_case_insensitive(self) -> None:
        store = Store.objects.create(name="Store A", code="sta")
        assert store.code == "STA"

    def test_store_str(self) -> None:
        store = Store.objects.create(name="Store A", code="STA")
        assert str(store) == "Store A"

    def test_store_inactive_filter(self) -> None:
        Store.objects.create(name="Active Store", code="SA", is_active=True)
        Store.objects.create(name="Inactive Store", code="SI", is_active=False)
        assert Store.objects.filter(is_active=True).count() == 1
        assert Store.objects.filter(is_active=False).count() == 1


@pytest.mark.django_db
class TestProductModel:
    """Product model tests."""

    def test_create_product(self, category) -> None:
        product = Product.objects.create(
            name="Laptop",
            description="Gaming laptop",
            category=category,
        )
        assert product.name == "Laptop"
        assert product.slug == "laptop"
        assert product.category == category
        assert product.is_active is True

    def test_product_slug_auto_generation(self, category) -> None:
        product = Product.objects.create(name="Gaming Laptop", category=category)
        assert product.slug == "gaming-laptop"

    def test_product_slug_uniqueness(self, category) -> None:
        Product.objects.create(name="Laptop", category=category)
        product2 = Product.objects.create(name="laptop", category=category)
        assert product2.slug == "laptop-1"

    def test_product_category_protect_on_delete(self, category) -> None:
        Product.objects.create(name="Laptop", category=category)
        with pytest.raises(ProtectedError):
            category.delete()

    def test_product_str(self, category) -> None:
        product = Product.objects.create(name="Laptop", category=category)
        assert str(product) == "Laptop"

    def test_product_inactive_filter(self, category) -> None:
        Product.objects.create(name="Active Product", category=category, is_active=True)
        Product.objects.create(name="Inactive Product", category=category, is_active=False)
        assert Product.objects.filter(is_active=True).count() == 1
        assert Product.objects.filter(is_active=False).count() == 1


@pytest.mark.django_db
class TestProductAttributeModel:
    """Product attribute model tests."""

    def test_create_attribute(self, product) -> None:
        attr = ProductAttribute.objects.create(
            product=product,
            name="Brand",
            value="Dell",
        )
        assert attr.name == "Brand"
        assert attr.value == "Dell"

    def test_attribute_unique_per_product(self, product) -> None:
        ProductAttribute.objects.create(product=product, name="Brand", value="Dell")
        with pytest.raises(IntegrityError):
            ProductAttribute.objects.create(product=product, name="Brand", value="HP")

    def test_attribute_same_name_different_products(self, category) -> None:
        product1 = Product.objects.create(name="Laptop 1", category=category)
        product2 = Product.objects.create(name="Laptop 2", category=category)
        ProductAttribute.objects.create(product=product1, name="Brand", value="Dell")
        ProductAttribute.objects.create(product=product2, name="Brand", value="HP")
        assert ProductAttribute.objects.count() == 2

    def test_attribute_str(self, product) -> None:
        attr = ProductAttribute.objects.create(product=product, name="Brand", value="Dell")
        assert "Dell" in str(attr)


@pytest.mark.django_db
class TestProductImageModel:
    """Product image model tests."""

    def create_test_image(self) -> SimpleUploadedFile:
        """Create a simple test image."""
        img = Image.new("RGB", (100, 100), color="red")
        from io import BytesIO

        buffer = BytesIO()
        img.save(buffer, format="JPEG")
        buffer.seek(0)
        return SimpleUploadedFile("test.jpg", buffer.read(), content_type="image/jpeg")

    def test_create_image(self, product) -> None:
        image_file = self.create_test_image()
        image = ProductImage.objects.create(
            product=product,
            image=image_file,
            alt_text="Test image",
            is_primary=True,
        )

        assert image.product == product
        assert image.alt_text == "Test image"
        assert image.is_primary is True

    def test_only_one_primary_per_product(self, product) -> None:
        image_file1 = self.create_test_image()
        image_file2 = self.create_test_image()

        img1 = ProductImage.objects.create(product=product, image=image_file1, is_primary=True)
        img2 = ProductImage.objects.create(product=product, image=image_file2, is_primary=True)

        img1.refresh_from_db()
        assert img1.is_primary is False
        assert img2.is_primary is True


@pytest.mark.django_db
class TestProductStoreModel:
    """Product-Store association model tests."""

    def test_create_association(self, product, store) -> None:
        assoc = ProductStore.objects.create(
            product=product,
            store=store,
            price=Decimal("15.00"),
            quantity=100,
        )
        assert assoc.product == product
        assert assoc.store == store
        assert assoc.price == Decimal("15.00")
        assert assoc.quantity == 100
        assert assoc.is_available is True

    def test_unique_product_store_constraint(self, product, store) -> None:
        ProductStore.objects.create(
            product=product, store=store, price=Decimal("15.00"), quantity=100
        )
        # Try to create another association with same product and store
        with pytest.raises((ValidationError, IntegrityError)):
            ProductStore.objects.create(
                product=product, store=store, price=Decimal("20.00"), quantity=50
            )

    def test_negative_price_rejected(self, product, store) -> None:
        from django.core.exceptions import ValidationError

        assoc = ProductStore(product=product, store=store, price=Decimal("-5.00"), quantity=100)
        with pytest.raises(ValidationError):
            assoc.full_clean()

    def test_negative_quantity_rejected(self, product, store) -> None:
        from django.core.exceptions import ValidationError

        assoc = ProductStore(product=product, store=store, price=Decimal("15.00"), quantity=-1)
        with pytest.raises(ValidationError):
            assoc.full_clean()

    def test_price_decimal_precision(self, product, store) -> None:
        # Create a different store for this test to avoid unique constraint
        store2 = Store.objects.create(name="Store B", code="STB")
        assoc = ProductStore.objects.create(
            product=product,
            store=store2,
            price=Decimal("15.999"),
            quantity=100,
        )
        # Should round to 2 decimal places
        assert assoc.price == Decimal("16.00")

    def test_str_representation(self, product, store) -> None:
        assoc = ProductStore.objects.create(
            product=product, store=store, price=Decimal("15.00"), quantity=100
        )
        assert "15.00" in str(assoc)
        assert product.name in str(assoc)
        assert store.name in str(assoc)
