"""Catalog models: categories, stores, products, attributes, images and pricing."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    """Product category with hierarchical support."""

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=["is_active"], name="category_active_idx"),
            models.Index(fields=["parent", "is_active"], name="category_parent_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = base_slug
            counter = 1
            while Category.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    @property
    def full_path(self) -> str:
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name


class Store(models.Model):
    """Physical or business location where products are available."""

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"], name="store_active_idx"),
            models.Index(fields=["code"], name="store_code_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)


class Product(models.Model):
    """Product with category, attributes, images and store associations."""

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=210, unique=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"], name="product_active_idx"),
            models.Index(fields=["category", "is_active"], name="product_category_idx"),
            models.Index(fields=["slug"], name="product_slug_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = base_slug
            counter = 1
            while Product.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class ProductAttribute(models.Model):
    """Flexible key-value attributes for a product."""

    id = models.BigAutoField(primary_key=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="attributes",
    )
    name = models.CharField(max_length=100)
    value = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "name"],
                name="unique_product_attribute_name",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "name"], name="product_attr_name_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} - {self.name}: {self.value}"


def product_image_upload_path(instance: "ProductImage", filename: str) -> str:
    """Generate upload path for product images."""
    ext = filename.split(".")[-1].lower()
    return f"products/{instance.product_id}/images/{uuid.uuid4()}.{ext}"


class ProductImage(models.Model):
    """Product image with metadata."""

    id = models.BigAutoField(primary_key=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to=product_image_upload_path)
    alt_text = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product", "display_order", "id"]
        indexes = [
            models.Index(fields=["product", "is_primary"], name="product_img_primary_idx"),
        ]

    def __str__(self) -> str:
        return f"Image for {self.product.name} ({'primary' if self.is_primary else 'secondary'})"

    def save(self, *args, **kwargs):
        # Ensure only one primary image per product
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(
                pk=self.pk
            ).update(is_primary=False)
        super().save(*args, **kwargs)


class ProductStore(models.Model):
    """Product-Store association with store-specific price and inventory."""

    id = models.BigAutoField(primary_key=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="store_associations",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="product_associations",
    )
    price = models.DecimalField(max_digits=12, decimal_places=4)
    quantity = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product", "store"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "store"],
                name="unique_product_store",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "is_available"], name="prod_store_avail_idx"),
            models.Index(fields=["store", "is_available"], name="store_prod_avail_idx"),
            models.Index(fields=["price"], name="prod_store_price_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} @ {self.store.name} - {self.price}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.price is not None and self.price < 0:
            raise ValidationError({"price": "Price must be greater than or equal to zero."})
        if self.quantity is not None and self.quantity < 0:
            raise ValidationError({"quantity": "Quantity cannot be negative."})
        # Round price to 2 decimal places for storage
        if self.price is not None:
            self.price = self.price.quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)