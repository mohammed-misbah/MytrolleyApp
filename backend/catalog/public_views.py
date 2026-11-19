"""Anonymous, read-only customer catalogue endpoints.

All visibility rules are centralized here so no public endpoint can leak
inactive, hidden or soft-deleted records. Administrative views in
``catalog/views.py`` are untouched and keep their existing protections.
"""

from __future__ import annotations

import mimetypes
from collections.abc import Sequence
from typing import Any

from django.core.files.storage import default_storage
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Category, Product, ProductAttribute, ProductImage, ProductStore, Store
from catalog.public_serializers import (
    PublicCategorySerializer,
    PublicImageSerializer,
    PublicProductDetailSerializer,
    PublicProductListSerializer,
    PublicProductQuerySerializer,
    PublicStoreSerializer,
)
from core.schema import ErrorEnvelopeSerializer

PUBLIC_ERROR_RESPONSES = {
    400: ErrorEnvelopeSerializer,
    404: ErrorEnvelopeSerializer,
}


def public_category_ids() -> set[int]:
    """Return ids of active categories whose entire ancestry is active."""
    categories = {row["id"]: row for row in Category.objects.values("id", "parent_id", "is_active")}
    visible: set[int] = set()
    for category_id in categories:
        current: int | None = category_id
        seen: set[int] = set()
        ok = True
        while current is not None:
            if current in seen or current not in categories:
                ok = False
                break
            row = categories[current]
            if not row["is_active"]:
                ok = False
                break
            seen.add(current)
            current = row["parent_id"]
        if ok:
            visible.add(category_id)
    return visible


def public_store_queryset() -> Any:
    """Active stores only."""
    return Store.objects.filter(is_active=True)


def public_product_queryset(category_ids: set[int] | None = None) -> Any:
    """Products visible to customers.

    A product must be active, undeleted, in a publicly visible category and
    available through at least one active store association.
    """
    visible = public_category_ids() if category_ids is None else category_ids
    return Product.objects.filter(
        is_active=True,
        deleted_at__isnull=True,
        category_id__in=visible,
        store_associations__is_available=True,
        store_associations__store__is_active=True,
    )


def is_product_public(product: Product) -> bool:
    """Single-product visibility check used by the image-serving endpoint."""
    if not product.is_active or product.deleted_at is not None:
        return False
    if product.category_id not in public_category_ids():
        return False
    return ProductStore.objects.filter(
        product=product,
        is_available=True,
        store__is_active=True,
    ).exists()


def _image_prefetch() -> Prefetch:
    return Prefetch(
        "images",
        queryset=ProductImage.objects.order_by("-is_primary", "display_order", "id"),
    )


def _association_prefetch(store_id: int | None = None) -> Prefetch:
    associations = ProductStore.objects.filter(
        is_available=True, store__is_active=True
    ).select_related("store")
    if store_id is not None:
        associations = associations.filter(store_id=store_id)
    return Prefetch("store_associations", queryset=associations)


class PublicAPIView(APIView):
    """Public endpoints are anonymous, read-only and unauthenticated."""

    authentication_classes: Sequence[type[BaseAuthentication]] = ()
    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)


@extend_schema(
    tags=["Public Catalogue"],
    summary="List active stores",
    description="Anonymous read-only list of active stores and their public product counts.",
    auth=[],
    responses={200: PublicStoreSerializer(many=True), **PUBLIC_ERROR_RESPONSES},
)
class PublicStoreListView(PublicAPIView):
    """Active stores for customer browsing."""

    def get(self, request: Request) -> Response:
        visible = public_category_ids()
        stores = (
            public_store_queryset()
            .annotate(
                public_product_count=Count(
                    "product_associations",
                    filter=Q(
                        product_associations__is_available=True,
                        product_associations__product__is_active=True,
                        product_associations__product__deleted_at__isnull=True,
                        product_associations__product__category_id__in=visible,
                    ),
                    distinct=True,
                )
            )
            .order_by("name")
        )
        return Response(PublicStoreSerializer(stores, many=True).data)


@extend_schema(
    tags=["Public Catalogue"],
    summary="List visible categories",
    description="Anonymous read-only list of active categories with active ancestors only.",
    auth=[],
    responses={200: PublicCategorySerializer(many=True), **PUBLIC_ERROR_RESPONSES},
)
class PublicCategoryListView(PublicAPIView):
    """Categories safe to show to customers."""

    def get(self, request: Request) -> Response:
        visible = public_category_ids()
        categories = (
            Category.objects.filter(id__in=visible)
            .select_related("parent")
            .annotate(
                public_product_count=Count(
                    "products",
                    filter=Q(
                        products__is_active=True,
                        products__deleted_at__isnull=True,
                        products__store_associations__is_available=True,
                        products__store_associations__store__is_active=True,
                    ),
                    distinct=True,
                )
            )
            .order_by("name")
        )
        all_categories = list(
            Category.objects.filter(id__in=visible).only("id", "parent_id", "name", "slug")
        )
        context = {
            "request": request,
            "visible_category_ids": visible,
            "all_categories": all_categories,
        }
        return Response(PublicCategorySerializer(categories, many=True, context=context).data)


@extend_schema(
    tags=["Public Catalogue"],
    summary="List public products",
    description=(
        "Anonymous read-only, paginated product discovery. Supports search, category, "
        "store, price and ordering parameters. Visibility rules cannot be relaxed by "
        "query parameters."
    ),
    auth=[],
    parameters=[
        OpenApiParameter("search", str, description="Case-insensitive name/description search"),
        OpenApiParameter("category", int, description="Category id"),
        OpenApiParameter("store", int, description="Active store id"),
        OpenApiParameter("page", int, description="Page number"),
        OpenApiParameter("page_size", int, description="Page size, maximum 100"),
        OpenApiParameter(
            "ordering",
            str,
            enum=["name", "-name", "created_at", "-created_at", "price", "-price"],
            description="price ordering requires a selected store",
        ),
        OpenApiParameter("min_price", str, description="Minimum price in the selected store"),
        OpenApiParameter("max_price", str, description="Maximum price in the selected store"),
    ],
    responses={200: PublicProductListSerializer(many=True), **PUBLIC_ERROR_RESPONSES},
)
class PublicProductListView(PublicAPIView):
    """Paginated public product catalogue."""

    def get(self, request: Request) -> Response:
        query = PublicProductQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data

        visible = public_category_ids()
        products = public_product_queryset(visible)

        search = params.get("search")
        if search:
            products = products.filter(Q(name__icontains=search) | Q(description__icontains=search))

        category_id = params.get("category")
        if category_id is not None:
            products = products.filter(category_id=category_id)

        store_id = params.get("store")
        if store_id is not None:
            products = products.filter(store_associations__store_id=store_id)

        minimum = params.get("min_price")
        maximum = params.get("max_price")
        if minimum is not None:
            products = products.filter(store_associations__price__gte=minimum)
        if maximum is not None:
            products = products.filter(store_associations__price__lte=maximum)

        ordering = params.get("ordering", "name")
        if ordering in ("price", "-price") and store_id is not None:
            products = products.order_by(
                f"{'-' if ordering.startswith('-') else ''}store_associations__price"
            )
        else:
            products = products.order_by(ordering)

        products = products.distinct()
        total = products.count()
        products = products.select_related("category").prefetch_related(
            _image_prefetch(), _association_prefetch(store_id)
        )

        page = params.get("page", 1)
        page_size = params.get("page_size", 20)
        offset = (page - 1) * page_size
        serializer = PublicProductListSerializer(
            products[offset : offset + page_size],
            many=True,
            context={"request": request, "store_id": store_id},
        )
        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "results": serializer.data,
            }
        )


@extend_schema(
    tags=["Public Catalogue"],
    summary="Public product details",
    description=(
        "Anonymous read-only product detail with attributes, images and eligible store pricing."
    ),
    auth=[],
    parameters=[OpenApiParameter("store", int, description="Active store id")],
    responses={200: PublicProductDetailSerializer, **PUBLIC_ERROR_RESPONSES},
)
class PublicProductDetailView(PublicAPIView):
    """Complete customer-facing product detail."""

    def get(self, request: Request, pk: int) -> Response:
        store_id: int | None = None
        if "store" in request.query_params:
            try:
                store_id = int(request.query_params["store"])
            except (TypeError, ValueError):
                raise serializers.ValidationError({"store": "Enter a valid store id."}) from None
            if not Store.objects.filter(pk=store_id, is_active=True).exists():
                raise serializers.ValidationError({"store": "Select a valid active store."})

        visible = public_category_ids()
        products = (
            public_product_queryset(visible)
            .filter(pk=pk)
            .select_related("category")
            .prefetch_related(
                _image_prefetch(),
                Prefetch("attributes", queryset=ProductAttribute.objects.order_by("name")),
                # Keep every eligible store in the nested list; the serializer
                # selects the requested store from this same association set.
                _association_prefetch(),
            )
            .distinct()
        )
        product = products.first()
        if product is None:
            raise Http404
        serializer = PublicProductDetailSerializer(
            product, context={"request": request, "store_id": store_id}
        )
        return Response(serializer.data)


@extend_schema(
    tags=["Public Catalogue"],
    summary="Public product image",
    description="Serves an image only when its product is publicly visible. Anonymous read-only.",
    auth=[],
    responses={200: PublicImageSerializer, 404: ErrorEnvelopeSerializer},
)
class PublicImageView(PublicAPIView):
    """Visibility-checked image serving; no arbitrary file paths are accepted."""

    def get(self, request: Request, image_id: int) -> FileResponse:
        image = (
            ProductImage.objects.select_related("product__category")
            .prefetch_related("product__store_associations__store")
            .filter(pk=image_id)
            .first()
        )
        if image is None or not is_product_public(image.product):
            raise Http404
        # Storage-agnostic: works with local files and private S3/Spaces objects.
        name = image.image.name
        if not name or not default_storage.exists(name):
            raise Http404
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        return FileResponse(default_storage.open(name, "rb"), content_type=content_type)
