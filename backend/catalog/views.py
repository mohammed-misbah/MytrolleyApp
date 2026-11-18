"""Catalog views for categories, stores, products, attributes, images and pricing."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasBusinessPermission
from catalog.models import Category, Product, ProductAttribute, ProductImage, ProductStore, Store
from catalog.serializers import (
    CategorySerializer,
    CategoryWriteSerializer,
    ProductAttributeSerializer,
    ProductAttributeWriteSerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductImageWriteSerializer,
    ProductListSerializer,
    ProductSearchSerializer,
    ProductStoreSerializer,
    ProductStoreWriteSerializer,
    ProductWriteSerializer,
    StoreSerializer,
    StoreWriteSerializer,
)
from core.schema import ErrorEnvelopeSerializer
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

_logger = logging.getLogger("mytrolley.catalog")


class CategoryListCreateView(APIView):
    """List and create categories."""

    permission_classes = [IsAuthenticated, HasBusinessPermission]
    permission_required = "accounts.manage_catalog"

    @extend_schema(
        tags=["Categories"],
        summary="List categories",
        description="List all categories with optional filtering by active status.",
        parameters=[
            OpenApiParameter(
                name="is_active",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter by active status",
            ),
        ],
        responses={
            200: CategorySerializer(many=True),
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        is_active = request.query_params.get("is_active")
        queryset = Category.objects.select_related("parent").prefetch_related("children")

        if is_active is not None:
            if is_active.lower() in ("true", "1"):
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() in ("false", "0"):
                queryset = queryset.filter(is_active=False)

        serializer = CategorySerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["Categories"],
        summary="Create category",
        description="Create a new category. Requires manage_catalog permission.",
        request=CategoryWriteSerializer,
        responses={
            201: CategorySerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = CategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return Response(
            CategorySerializer(category).data,
            status=status.HTTP_201_CREATED,
        )


class CategoryDetailView(APIView):
    """Retrieve, update or delete a category."""

    permission_classes = [IsAuthenticated, HasBusinessPermission]
    permission_required = "accounts.manage_catalog"

    def get_object(self, pk: int) -> Category:
        try:
            return Category.objects.select_related("parent").prefetch_related("children").get(pk=pk)
        except Category.DoesNotExist:
            raise Http404

    @extend_schema(
        tags=["Categories"],
        summary="Retrieve category",
        description="Retrieve a single category by ID.",
        responses={
            200: CategorySerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def get(self, request: Request, pk: int) -> Response:
        category = self.get_object(pk)
        serializer = CategorySerializer(category)
        return Response(serializer.data)

    @extend_schema(
        tags=["Categories"],
        summary="Update category",
        description="Update a category. Requires manage_catalog permission.",
        request=CategoryWriteSerializer,
        responses={
            200: CategorySerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def patch(self, request: Request, pk: int) -> Response:
        category = self.get_object(pk)
        serializer = CategoryWriteSerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return Response(CategorySerializer(category).data)

    @extend_schema(
        tags=["Categories"],
        summary="Delete category",
        description="Delete a category. Fails if category has products.",
        responses={
            204: None,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
            409: ErrorEnvelopeSerializer,
        },
    )
    def delete(self, request: Request, pk: int) -> Response:
        category = self.get_object(pk)
        if category.products.exists():
            return Response(
                {"error": {"code": "CONFLICT", "message": "Cannot delete category with associated products."}},
                status=status.HTTP_409_CONFLICT,
            )
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StoreListCreateView(APIView):
    """List and create stores."""

    permission_classes = [IsAuthenticated, HasBusinessPermission]
    permission_required = "accounts.manage_catalog"

    @extend_schema(
        tags=["Stores"],
        summary="List stores",
        description="List all stores with optional filtering by active status.",
        parameters=[
            OpenApiParameter(
                name="is_active",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter by active status",
            ),
        ],
        responses={
            200: StoreSerializer(many=True),
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        is_active = request.query_params.get("is_active")
        queryset = Store.objects.all()

        if is_active is not None:
            if is_active.lower() in ("true", "1"):
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() in ("false", "0"):
                queryset = queryset.filter(is_active=False)

        serializer = StoreSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["Stores"],
        summary="Create store",
        description="Create a new store. Requires manage_catalog permission.",
        request=StoreWriteSerializer,
        responses={
            201: StoreSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = StoreWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = serializer.save()
        return Response(StoreSerializer(store).data, status=status.HTTP_201_CREATED)


class StoreDetailView(APIView):
    """Retrieve, update or delete a store."""

    permission_classes = [IsAuthenticated, HasBusinessPermission]
    permission_required = "accounts.manage_catalog"

    def get_object(self, pk: int) -> Store:
        try:
            return Store.objects.get(pk=pk)
        except Store.DoesNotExist:
            raise Http404

    @extend_schema(
        tags=["Stores"],
        summary="Retrieve store",
        description="Retrieve a single store by ID.",
        responses={
            200: StoreSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def get(self, request: Request, pk: int) -> Response:
        store = self.get_object(pk)
        serializer = StoreSerializer(store)
        return Response(serializer.data)

    @extend_schema(
        tags=["Stores"],
        summary="Update store",
        description="Update a store. Requires manage_catalog permission.",
        request=StoreWriteSerializer,
        responses={
            200: StoreSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def patch(self, request: Request, pk: int) -> Response:
        store = self.get_object(pk)
        serializer = StoreWriteSerializer(store, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        store = serializer.save()
        return Response(StoreSerializer(store).data)

    @extend_schema(
        tags=["Stores"],
        summary="Delete store",
        description="Delete a store. Fails if store has product associations.",
        responses={
            204: None,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
            409: ErrorEnvelopeSerializer,
        },
    )
    def delete(self, request: Request, pk: int) -> Response:
        store = self.get_object(pk)
        if store.product_associations.exists():
            return Response(
                {"error": {"code": "CONFLICT", "message": "Cannot delete store with associated products."}},
                status=status.HTTP_409_CONFLICT,
            )
        store.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductListCreateView(APIView):
    """List and create products with search, filter, sort and pagination."""

    permission_classes = [IsAuthenticated, HasBusinessPermission]
    permission_required = "accounts.manage_catalog"

    @extend_schema(
        tags=["Products"],
        summary="List products",
        description=(
            "List products with support for search, filtering, sorting and pagination.\n\n"
            "**Query Parameters:**\n"
            "- `search`: Search in product name and description\n"
            "- `category`: Filter by category ID\n"
            "- `store`: Filter by store ID (shows products available in that store)\n"
            "- `is_active`: Filter by active status\n"
            "- `is_available`: Filter by availability in the selected store\n"
            "- `min_price` / `max_price`: Filter by price range (requires store parameter)\n"
            "- `ordering`: Sort by name, created_at, or price (price requires store)\n"
            "- `page` / `page_size`: Pagination"
        ),
        parameters=[
            OpenApiParameter("search", str, OpenApiParameter.QUERY, description="Search in name and description"),
            OpenApiParameter("category", int, OpenApiParameter.QUERY, description="Category ID"),
            OpenApiParameter("store", int, OpenApiParameter.QUERY, description="Store ID"),
            OpenApiParameter("is_active", bool, OpenApiParameter.QUERY, description="Filter by active status"),
            OpenApiParameter("is_available", bool, OpenApiParameter.QUERY, description="Filter by availability in store"),
            OpenApiParameter("min_price", Decimal, OpenApiParameter.QUERY, description="Minimum price"),
            OpenApiParameter("max_price", Decimal, OpenApiParameter.QUERY, description="Maximum price"),
            OpenApiParameter("ordering", str, OpenApiParameter.QUERY, enum=["name", "-name", "created_at", "-created_at", "price", "-price"]),
            OpenApiParameter("page", int, OpenApiParameter.QUERY, description="Page number"),
            OpenApiParameter("page_size", int, OpenApiParameter.QUERY, description="Page size (max 100)"),
        ],
        responses={
            200: ProductListSerializer(many=True),
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        search_serializer = ProductSearchSerializer(data=request.query_params)
        search_serializer.is_valid(raise_exception=True)
        params = search_serializer.validated_data

        queryset = Product.objects.select_related("category").prefetch_related("images", "store_associations__store")

        if params.get("search"):
            search_term = params["search"]
            queryset = queryset.filter(
                Q(name__icontains=search_term) | Q(description__icontains=search_term)
            )

        if params.get("category"):
            queryset = queryset.filter(category_id=params["category"])

        if params.get("store"):
            store_id = params["store"]
            queryset = queryset.filter(
                store_associations__store_id=store_id,
                store_associations__is_available=True,
            )

        if params.get("is_active") is not None:
            queryset = queryset.filter(is_active=params["is_active"])

        if params.get("is_available") is not None and params.get("store"):
            store_id = params["store"]
            if params["is_available"]:
                queryset = queryset.filter(
                    store_associations__store_id=store_id,
                    store_associations__is_available=True,
                )
            else:
                queryset = queryset.exclude(
                    store_associations__store_id=store_id,
                    store_associations__is_available=True,
                )

        if params.get("min_price") is not None and params.get("store"):
            queryset = queryset.filter(
                store_associations__store_id=params["store"],
                store_associations__price__gte=params["min_price"],
            )

        if params.get("max_price") is not None and params.get("store"):
            queryset = queryset.filter(
                store_associations__store_id=params["store"],
                store_associations__price__lte=params["max_price"],
            )

        ordering = params.get("ordering", "name")
        if ordering in ("price", "-price") and params.get("store"):
            # Annotate with store-specific price for ordering
            from django.db.models import F
            queryset = queryset.filter(store_associations__store_id=params["store"]).annotate(
                store_price=F("store_associations__price")
            ).order_by(f"{'-' if ordering.startswith('-') else ''}store_price")
        else:
            queryset = queryset.order_by(ordering)

        # Pagination
        page = params.get("page", 1)
        page_size = min(params.get("page_size", 20), 100)
        offset = (page - 1) * page_size

        total = queryset.distinct().count()
        products = queryset.distinct()[offset : offset + page_size]

        if params.get("search"):
            search_term = params["search"]
            queryset = queryset.filter(
                Q(name__icontains=search_term) | Q(description__icontains=search_term)
            )

        if params.get("category"):
            queryset = queryset.filter(category_id=params["category"])

        if params.get("store"):
            store_id = params["store"]
            queryset = queryset.filter(
                store_associations__store_id=store_id,
                store_associations__is_available=True,
            )

        if params.get("is_active") is not None:
            queryset = queryset.filter(is_active=params["is_active"])

        if params.get("is_available") is not None and params.get("store"):
            store_id = params["store"]
            if params["is_available"]:
                queryset = queryset.filter(
                    store_associations__store_id=store_id,
                    store_associations__is_available=True,
                )
            else:
                queryset = queryset.exclude(
                    store_associations__store_id=store_id,
                    store_associations__is_available=True,
                )

        if params.get("min_price") is not None and params.get("store"):
            queryset = queryset.filter(
                store_associations__store_id=params["store"],
                store_associations__price__gte=params["min_price"],
            )

        if params.get("max_price") is not None and params.get("store"):
            queryset = queryset.filter(
                store_associations__store_id=params["store"],
                store_associations__price__lte=params["max_price"],
            )

        ordering = params.get("ordering", "name")
        if ordering in ("price", "-price") and params.get("store"):
            # Annotate with store-specific price for ordering
            from django.db.models import F
            queryset = queryset.filter(store_associations__store_id=params["store"]).annotate(
                store_price=F("store_associations__price")
            ).order_by(f"{'-' if ordering.startswith('-') else ''}store_price")
        else:
            queryset = queryset.order_by(ordering)

        # Pagination
        page = params.get("page", 1)
        page_size = min(params.get("page_size", 20), 100)
        offset = (page - 1) * page_size

        total = queryset.distinct().count()
        products = queryset.distinct()[offset : offset + page_size]

        serializer = ProductListSerializer(
            products,
            many=True,
            context={"request": request, "store_id": params.get("store")},
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
        tags=["Products"],
        summary="Create product",
        description="Create a new product with category. Requires manage_catalog permission.",
        request=ProductWriteSerializer,
        responses={
            201: ProductDetailSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return Response(
            ProductDetailSerializer(product, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ProductDetailView(APIView):
    """Retrieve, update or delete a product."""

    permission_classes = [IsAuthenticated, HasBusinessPermission]
    permission_required = "accounts.manage_catalog"

    def get_object(self, pk: int) -> Product:
        try:
            return Product.objects.select_related("category").prefetch_related(
                "attributes",
                "images",
                "store_associations__store",
            ).get(pk=pk)
        except Product.DoesNotExist:
            raise Http404

    @extend_schema(
        tags=["Products"],
        summary="Retrieve product",
        description="Retrieve a single product with all nested relationships.",
        responses={
            200: ProductDetailSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def get(self, request: Request, pk: int) -> Response:
        product = self.get_object(pk)
        serializer = ProductDetailSerializer(product, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        tags=["Products"],
        summary="Update product",
        description="Update a product. Requires manage_catalog permission.",
        request=ProductWriteSerializer,
        responses={
            200: ProductDetailSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def patch(self, request: Request, pk: int) -> Response:
        product = self.get_object(pk)
        serializer = ProductWriteSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return Response(ProductDetailSerializer(product, context={"request": request}).data)

    @extend_schema(
        tags=["Products"],
        summary="Delete product",
        description="Delete a product. Sets is_active to false instead of hard delete.",
        responses={
            204: None,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def delete(self, request: Request, pk: int) -> Response:
        product = self.get_object(pk)
        product.is_active = False
        product.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductAttributeListCreateView(APIView):
    """List and create product attributes."""

    permission_classes = [IsAuthenticated, HasBusinessPermission]
    permission_required = "accounts.manage_catalog"

    def get_product(self, product_id: int) -> Product:
        try:
            return Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise Http404

    @extend_schema(
        tags=["Product Attributes"],
        summary="List product attributes",
        description="List all attributes for a product.",
        responses={
            200: ProductAttributeSerializer(many=True),
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def get(self, request: Request, product_id: int) -> Response:
        product = self.get_product(product_id)
        attributes = product.attributes.all()
        serializer = ProductAttributeSerializer(attributes, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["Product Attributes"],
        summary="Create product attribute",
        description="Create a new attribute for a product. Requires manage_catalog permission.",
        request=ProductAttributeWriteSerializer,
        responses={
            201: ProductAttributeSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def post(self, request: Request, product_id: int) -> Response:
        product = self.get_product(product_id)
        serializer = ProductAttributeWriteSerializer(data=request.data, context={"product": product})
        serializer.is_valid(raise_exception=True)
        attribute = serializer.save(product=product)
        return Response(
            ProductAttributeSerializer(attribute).data,
            status=status.HTTP_201_CREATED,
        )


class ProductAttributeDetailView(APIView):
    """Retrieve, update or delete a product attribute."""

    permission_classes = [IsAuthenticated, HasBusinessPermission]
    permission_required = "accounts.manage_catalog"

    def get_product(self, product_id: int) -> Product:
        try:
            return Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise Http404

    def get_attribute(self, product: Product, attr_id: int) -> ProductAttribute:
        try:
            return product.attributes.get(pk=attr_id)
        except ProductAttribute.DoesNotExist:
            raise Http404

    @extend_schema(
        tags=["Product Attributes"],
        summary="Retrieve product attribute",
        description="Retrieve a single attribute for a product.",
        responses={
            200: ProductAttributeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def get(self, request: Request, product_id: int, attr_id: int) -> Response:
        product = self.get_product(product_id)
        attribute = self.get_attribute(product, attr_id)
        serializer = ProductAttributeSerializer(attribute)
        return Response(serializer.data)

    @extend_schema(
        tags=["Product Attributes"],
        summary="Update product attribute",
        description="Update a product attribute. Requires manage_catalog permission.",
        request=ProductAttributeWriteSerializer,
        responses={
            200: ProductAttributeSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def patch(self, request: Request, product_id: int, attr_id: int) -> Response:
        product = self.get_product(product_id)
        attribute = self.get_attribute(product, attr_id)
        serializer = ProductAttributeWriteSerializer(attribute, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        attribute = serializer.save()
        return Response(ProductAttributeSerializer(attribute).data)

    @extend_schema(
        tags=["Product Attributes"],
        summary="Delete product attribute",
        description="Delete a product attribute. Requires manage_catalog permission.",
        responses={
            204: None,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def delete(self, request: Request, product_id: int, attr_id: int) -> Response:
        product = self.get_product(product_id)
        attribute = self.get_attribute(product, attr_id)
        attribute.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductImageListCreateView(APIView):
    """List and upload product images."""

    permission_classes = [IsAuthenticated, HasBusinessPermission]
    permission_required = "accounts.manage_catalog"
    parser_classes = [MultiPartParser, FormParser]

    def get_product(self, product_id: int) -> Product:
        try:
            return Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise Http404

    @extend_schema(
        tags=["Product Images"],
        summary="List product images",
        description="List all images for a product.",
        responses={
            200: ProductImageSerializer(many=True),
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def get(self, request: Request, product_id: int) -> Response:
        product = self.get_product(product_id)
        images = product.images.all()
        serializer = ProductImageSerializer(images, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        tags=["Product Images"],
        summary="Upload product image",
        description="Upload a new image for a product. Requires manage_catalog permission.",
        request=ProductImageWriteSerializer,
        responses={
            201: ProductImageSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def post(self, request: Request, product_id: int) -> Response:
        product = self.get_product(product_id)
        serializer = ProductImageWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.save(product=product)
        return Response(
            ProductImageSerializer(image, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ProductImageDetailView(APIView):
    """Retrieve, update or delete a product image."""

    permission_classes = [IsAuthenticated, HasBusinessPermission]
    permission_required = "accounts.manage_catalog"
    parser_classes = [MultiPartParser, FormParser]

    def get_product(self, product_id: int) -> Product:
        try:
            return Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise Http404

    def get_image(self, product: Product, image_id: int) -> ProductImage:
        try:
            return product.images.get(pk=image_id)
        except ProductImage.DoesNotExist:
            raise Http404

    @extend_schema(
        tags=["Product Images"],
        summary="Retrieve product image",
        description="Retrieve a single image for a product.",
        responses={
            200: ProductImageSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def get(self, request: Request, product_id: int, image_id: int) -> Response:
        product = self.get_product(product_id)
        image = self.get_image(product, image_id)
        serializer = ProductImageSerializer(image, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        tags=["Product Images"],
        summary="Update product image",
        description="Update a product image metadata. Requires manage_catalog permission.",
        request=ProductImageWriteSerializer,
        responses={
            200: ProductImageSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def patch(self, request: Request, product_id: int, image_id: int) -> Response:
        product = self.get_product(product_id)
        image = self.get_image(product, image_id)
        serializer = ProductImageWriteSerializer(image, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        image = serializer.save()
        return Response(ProductImageSerializer(image, context={"request": request}).data)

    @extend_schema(
        tags=["Product Images"],
        summary="Delete product image",
        description="Delete a product image. Requires manage_catalog permission.",
        responses={
            204: None,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def delete(self, request: Request, product_id: int, image_id: int) -> Response:
        product = self.get_product(product_id)
        image = self.get_image(product, image_id)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductStoreListCreateView(APIView):
    """List and create product-store associations."""

    permission_classes = [IsAuthenticated, HasBusinessPermission]
    permission_required = "accounts.manage_catalog"

    def get_product(self, product_id: int) -> Product:
        try:
            return Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise Http404

    @extend_schema(
        tags=["Product Stores"],
        summary="List product-store associations",
        description="List all store associations for a product with price and quantity.",
        responses={
            200: ProductStoreSerializer(many=True),
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def get(self, request: Request, product_id: int) -> Response:
        product = self.get_product(product_id)
        associations = product.store_associations.select_related("store").all()
        serializer = ProductStoreSerializer(associations, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["Product Stores"],
        summary="Create product-store association",
        description=(
            "Associate a product with a store with price and quantity. "
            "Requires manage_catalog permission. "
            "Duplicate associations for the same product-store pair are rejected."
        ),
        request=ProductStoreWriteSerializer,
        responses={
            201: ProductStoreSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
            409: ErrorEnvelopeSerializer,
        },
    )
    def post(self, request: Request, product_id: int) -> Response:
        product = self.get_product(product_id)
        serializer = ProductStoreWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        store = serializer.validated_data["store"]
        if product.store_associations.filter(store=store).exists():
            return Response(
                {"error": {"code": "CONFLICT", "message": "This product is already associated with the selected store."}},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            association = serializer.save(product=product)

        return Response(
            ProductStoreSerializer(association).data,
            status=status.HTTP_201_CREATED,
        )


class ProductStoreDetailView(APIView):
    """Retrieve, update or delete a product-store association."""

    permission_classes = [IsAuthenticated, HasBusinessPermission]
    permission_required = "accounts.manage_catalog"

    def get_product(self, product_id: int) -> Product:
        try:
            return Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise Http404

    def get_association(self, product: Product, assoc_id: int) -> ProductStore:
        try:
            return product.store_associations.get(pk=assoc_id)
        except ProductStore.DoesNotExist:
            raise Http404

    @extend_schema(
        tags=["Product Stores"],
        summary="Retrieve product-store association",
        description="Retrieve a single product-store association.",
        responses={
            200: ProductStoreSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def get(self, request: Request, product_id: int, assoc_id: int) -> Response:
        product = self.get_product(product_id)
        association = self.get_association(product, assoc_id)
        serializer = ProductStoreSerializer(association)
        return Response(serializer.data)

    @extend_schema(
        tags=["Product Stores"],
        summary="Update product-store association",
        description=(
            "Update price, quantity or availability for a product-store association. "
            "Requires manage_catalog permission."
        ),
        request=ProductStoreWriteSerializer,
        responses={
            200: ProductStoreSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def patch(self, request: Request, product_id: int, assoc_id: int) -> Response:
        product = self.get_product(product_id)
        association = self.get_association(product, assoc_id)
        serializer = ProductStoreWriteSerializer(association, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Check if store is being changed (not allowed)
        if "store" in serializer.validated_data and serializer.validated_data["store"] != association.store:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "Cannot change store of an existing association."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        association = serializer.save()
        return Response(ProductStoreSerializer(association).data)

    @extend_schema(
        tags=["Product Stores"],
        summary="Delete product-store association",
        description="Remove a product from a store. Requires manage_catalog permission.",
        responses={
            204: None,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            404: ErrorEnvelopeSerializer,
        },
    )
    def delete(self, request: Request, product_id: int, assoc_id: int) -> Response:
        product = self.get_product(product_id)
        association = self.get_association(product, assoc_id)
        association.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)