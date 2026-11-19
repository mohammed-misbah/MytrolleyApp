"""Customer-safe serializers for the anonymous public catalogue.

These serializers intentionally expose only fields needed for product
discovery. Administrative fields (availability toggles, soft-deletion state,
internal paths and security metadata) are never included.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.urls import reverse
from rest_framework import serializers

from catalog.models import Category, Product, ProductImage, ProductStore, Store

# Parameters that could be used to relax the mandatory public visibility rules.
# They are rejected instead of silently ignored so clients cannot believe a
# filter was applied when it was not.
BLOCKED_PUBLIC_PARAMS = frozenset({"is_active", "is_available", "deleted_at", "is_primary"})


class PublicQuerySerializer(serializers.Serializer):
    """Validate and constrain customer-supplied query parameters."""

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if hasattr(data, "keys"):
            blocked = set(data.keys()) & BLOCKED_PUBLIC_PARAMS
            if blocked:
                raise serializers.ValidationError(
                    {
                        key: "This parameter is not supported on public endpoints."
                        for key in sorted(blocked)
                    }
                )
        return dict(super().to_internal_value(data))


class PublicImageSerializer(serializers.ModelSerializer):
    """A product image with a request-aware, anonymously loadable URL."""

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "image_url", "alt_text"]

    def get_image_url(self, obj: ProductImage) -> str:
        request = self.context.get("request")
        url = reverse("catalog:public-image", args=[obj.pk])
        if request is not None:
            return str(request.build_absolute_uri(url))
        return url


class PublicCategorySummarySerializer(serializers.ModelSerializer):
    """Minimal nested category representation used inside products and lists."""

    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class PublicStoreSummarySerializer(serializers.ModelSerializer):
    """Minimal nested store representation used inside product details."""

    class Meta:
        model = Store
        fields = ["id", "name", "code"]


class PublicStoreSerializer(serializers.ModelSerializer):
    """Customer-facing store with a count of currently public products."""

    product_count = serializers.IntegerField(read_only=True, source="public_product_count")

    class Meta:
        model = Store
        fields = ["id", "name", "code", "description", "address", "is_active", "product_count"]


class PublicCategorySerializer(serializers.ModelSerializer):
    """Customer-facing category with publicly visible child categories."""

    parent = PublicCategorySummarySerializer(read_only=True)
    children = serializers.SerializerMethodField()
    product_count = serializers.IntegerField(read_only=True, source="public_product_count")

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "parent",
            "is_active",
            "children",
            "product_count",
        ]

    def get_children(self, obj: Category) -> list[dict[str, Any]]:
        visible = self.context.get("visible_category_ids", set())
        categories = self.context.get("all_categories", [])
        children = [
            category
            for category in categories
            if category.parent_id == obj.id and category.pk in visible
        ]
        return list(PublicCategorySummarySerializer(children, many=True).data)


class PublicStorePriceSerializer(serializers.ModelSerializer):
    """One product-store association as seen by a customer."""

    store = PublicStoreSummarySerializer(read_only=True)

    class Meta:
        model = ProductStore
        fields = ["store", "price", "quantity", "is_available"]


class PublicProductListSerializer(serializers.ModelSerializer):
    """Product row for the public listing endpoint."""

    category = PublicCategorySummarySerializer(read_only=True)
    primary_image = serializers.SerializerMethodField()
    starting_price = serializers.SerializerMethodField()
    selected_store_price = serializers.SerializerMethodField()
    available_stores = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "category",
            "is_active",
            "primary_image",
            "starting_price",
            "selected_store_price",
            "available_stores",
        ]

    def get_primary_image(self, obj: Product) -> dict[str, Any] | None:
        images = list(obj.images.all())
        if not images:
            return None
        image = next((item for item in images if item.is_primary), images[0])
        return PublicImageSerializer(image, context=self.context).data

    def get_available_stores(self, obj: Product) -> list[dict[str, Any]]:
        associations = list(obj.store_associations.all())
        return list(PublicStorePriceSerializer(associations, many=True, context=self.context).data)

    def get_starting_price(self, obj: Product) -> str | None:
        # No global price exists; this is explicitly the lowest eligible
        # store-specific price, calculated from the selected public records.
        prices = [association.price for association in obj.store_associations.all()]
        if not prices:
            return None
        return str(min(prices))

    def get_selected_store_price(self, obj: Product) -> dict[str, Any] | None:
        store_id = self.context.get("store_id")
        if store_id is None:
            return None
        association = next(
            (
                item
                for item in obj.store_associations.all()
                if item.store_id == store_id and item.is_available
            ),
            None,
        )
        if association is None:
            return None
        return PublicStorePriceSerializer(association, context=self.context).data


class PublicProductDetailSerializer(serializers.ModelSerializer):
    """Complete customer-facing product detail payload."""

    category = PublicCategorySummarySerializer(read_only=True)
    attributes = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    stores = serializers.SerializerMethodField()
    selected_store = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "category",
            "attributes",
            "images",
            "stores",
            "selected_store",
        ]

    def get_attributes(self, obj: Product) -> list[dict[str, Any]]:
        return [
            {"id": item.pk, "name": item.name, "value": item.value} for item in obj.attributes.all()
        ]

    def get_images(self, obj: Product) -> list[dict[str, Any]]:
        return list(PublicImageSerializer(obj.images.all(), many=True, context=self.context).data)

    def get_stores(self, obj: Product) -> list[dict[str, Any]]:
        stores = list(obj.store_associations.all())
        return list(PublicStorePriceSerializer(stores, many=True, context=self.context).data)

    def get_selected_store(self, obj: Product) -> dict[str, Any] | None:
        store_id = self.context.get("store_id")
        if store_id is None:
            return None
        association = next(
            (
                item
                for item in obj.store_associations.all()
                if item.store_id == store_id and item.is_available
            ),
            None,
        )
        if association is None:
            return None
        return PublicStorePriceSerializer(association, context=self.context).data


class PublicProductQuerySerializer(PublicQuerySerializer):
    """Query parameters accepted by the public product listing endpoint."""

    search = serializers.CharField(required=False, allow_blank=True)
    category = serializers.IntegerField(required=False, min_value=1)
    store = serializers.IntegerField(required=False, min_value=1)
    page = serializers.IntegerField(default=1, min_value=1)
    page_size = serializers.IntegerField(default=20, min_value=1, max_value=100)
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
    )
    min_price = serializers.DecimalField(
        max_digits=12, decimal_places=4, required=False, min_value=Decimal("0")
    )
    max_price = serializers.DecimalField(
        max_digits=12, decimal_places=4, required=False, min_value=Decimal("0")
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        store_id = attrs.get("store")
        price_requested = attrs.get("min_price") is not None or attrs.get("max_price") is not None
        price_ordering = attrs.get("ordering") in ("price", "-price")
        if (price_requested or price_ordering) and store_id is None:
            raise serializers.ValidationError(
                {"store": "Select a store to filter or sort by price."}
            )
        if store_id is not None and not Store.objects.filter(pk=store_id, is_active=True).exists():
            raise serializers.ValidationError({"store": "Select a valid active store."})
        minimum = attrs.get("min_price")
        maximum = attrs.get("max_price")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise serializers.ValidationError(
                {"min_price": "Minimum price cannot be greater than maximum price."}
            )
        return attrs
