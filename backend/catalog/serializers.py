"""Catalog serializers for categories, stores, products, attributes, images and pricing."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from catalog.models import Category, Product, ProductAttribute, ProductImage, ProductStore, Store
from core.serializers import StrictSerializer


class CategorySerializer(serializers.ModelSerializer):
    """Category serializer with nested children."""

    children = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "parent",
            "is_active",
            "created_at",
            "updated_at",
            "children",
            "product_count",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at", "children", "product_count"]

    def get_children(self, obj: Category) -> list[dict]:
        if obj.children.exists():
            return CategorySerializer(obj.children.filter(is_active=True), many=True).data
        return []

    def get_product_count(self, obj: Category) -> int:
        return obj.products.filter(is_active=True).count()


class CategoryWriteSerializer(serializers.ModelSerializer):
    """Category serializer for create/update operations."""

    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True)
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        required=False,
        allow_null=True,
    )
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = Category
        fields = ["name", "description", "parent", "is_active"]

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Category name cannot be empty.")
        return value.strip()


class StoreSerializer(serializers.ModelSerializer):
    """Store serializer."""

    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            "id",
            "name",
            "code",
            "description",
            "address",
            "is_active",
            "created_at",
            "updated_at",
            "product_count",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "product_count"]

    def get_product_count(self, obj: Store) -> int:
        return obj.product_associations.filter(is_available=True).count()


class StoreWriteSerializer(serializers.ModelSerializer):
    """Store serializer for create/update operations."""

    name = serializers.CharField(max_length=100)
    code = serializers.CharField(max_length=20)
    description = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = Store
        fields = ["name", "code", "description", "address", "is_active"]

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Store name cannot be empty.")
        return value.strip()

    def validate_code(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Store code cannot be empty.")
        value = value.strip().upper()
        # Check for duplicate code
        queryset = Store.objects.filter(code=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A store with this code already exists.")
        return value


class ProductAttributeSerializer(serializers.ModelSerializer):
    """Product attribute serializer."""

    class Meta:
        model = ProductAttribute
        fields = ["id", "name", "value", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductAttributeWriteSerializer(serializers.ModelSerializer):
    """Product attribute serializer for create/update operations."""

    name = serializers.CharField(max_length=100)
    value = serializers.CharField()

    class Meta:
        model = ProductAttribute
        fields = ["name", "value"]

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Attribute name cannot be empty.")
        return value.strip()

    def validate_value(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Attribute value cannot be empty.")
        return value.strip()

    def validate(self, attrs):
        # Check for duplicate attribute name for the same product
        product = self.context.get("product")
        if product:
            name = attrs.get("name", "").strip()
            queryset = ProductAttribute.objects.filter(product=product, name__iexact=name)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({"name": "An attribute with this name already exists for this product."})
        return attrs


class ProductImageSerializer(serializers.ModelSerializer):
    """Product image serializer."""

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = [
            "id",
            "image",
            "image_url",
            "alt_text",
            "display_order",
            "is_primary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "image_url", "created_at", "updated_at"]

    def get_image_url(self, obj: ProductImage) -> str:
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return ""


class ProductImageWriteSerializer(serializers.ModelSerializer):
    """Product image upload serializer."""

    class Meta:
        model = ProductImage
        fields = ["image", "alt_text", "display_order", "is_primary"]


class ProductStoreSerializer(serializers.ModelSerializer):
    """Product-Store association serializer."""

    store = StoreSerializer(read_only=True)
    store_id = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(),
        source="store",
        write_only=True,
    )

    class Meta:
        model = ProductStore
        fields = [
            "id",
            "store",
            "store_id",
            "price",
            "quantity",
            "is_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductStoreWriteSerializer(serializers.ModelSerializer):
    """Product-Store association serializer for create/update operations."""

    store_id = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(),
        source="store",
    )
    price = serializers.DecimalField(max_digits=12, decimal_places=4)
    quantity = serializers.IntegerField(min_value=0, default=0)
    is_available = serializers.BooleanField(default=True)

    class Meta:
        model = ProductStore
        fields = ["store_id", "price", "quantity", "is_available"]

    def validate_price(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("Price must be greater than or equal to zero.")
        return value


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight product serializer for list views."""

    category = serializers.StringRelatedField()
    primary_image = serializers.SerializerMethodField()
    store_price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "category",
            "is_active",
            "created_at",
            "updated_at",
            "primary_image",
            "store_price",
        ]

    def get_primary_image(self, obj: Product) -> dict | None:
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return ProductImageSerializer(primary, context=self.context).data
        first = obj.images.first()
        if first:
            return ProductImageSerializer(first, context=self.context).data
        return None

    def get_store_price(self, obj: Product) -> dict | None:
        """Get price for a specific store if provided in context."""
        store_id = self.context.get("store_id")
        if store_id:
            association = obj.store_associations.filter(store_id=store_id, is_available=True).first()
            if association:
                return ProductStoreSerializer(association, context=self.context).data
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed product serializer with nested relationships."""

    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
        write_only=True,
    )
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    store_associations = ProductStoreSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "category",
            "category_id",
            "is_active",
            "created_at",
            "updated_at",
            "attributes",
            "images",
            "store_associations",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class ProductWriteSerializer(serializers.ModelSerializer):
    """Product serializer for create/update operations."""

    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
    )
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = Product
        fields = ["name", "description", "category_id", "is_active"]

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Product name cannot be empty.")
        return value.strip()


class ProductSearchSerializer(serializers.Serializer):
    """Serializer for product search query parameters."""

    search = serializers.CharField(required=False, help_text="Search in name and description")
    category = serializers.IntegerField(required=False, help_text="Filter by category ID")
    store = serializers.IntegerField(required=False, help_text="Filter by store ID")
    is_active = serializers.BooleanField(required=False, help_text="Filter by active status")
    is_available = serializers.BooleanField(required=False, help_text="Filter by availability in store")
    min_price = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, help_text="Minimum price")
    max_price = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, help_text="Maximum price")
    ordering = serializers.ChoiceField(
        choices=[
            "name",
            "-name",
            "created_at",
            "-created_at",
            "price",
            "-price",
        ],
        required=False,
        default="name",
        help_text="Ordering field",
    )
    page = serializers.IntegerField(default=1, min_value=1)
    page_size = serializers.IntegerField(default=20, min_value=1, max_value=100)

    def to_internal_value(self, data):
        """Only include boolean fields in validated_data if they were explicitly provided."""
        # Check which boolean fields were explicitly provided
        provided_fields = set()
        if isinstance(data, dict):
            for field in ("is_active", "is_available"):
                if field in data:
                    provided_fields.add(field)
        
        ret = super().to_internal_value(data)
        
        # Remove boolean fields that weren't explicitly provided
        for field in ("is_active", "is_available"):
            if field not in provided_fields:
                ret.pop(field, None)
        
        return ret