"""Catalog URL routes, mounted under /api/v1/."""

from __future__ import annotations

from django.urls import path

from catalog.public_views import (
    PublicCategoryListView,
    PublicImageView,
    PublicProductDetailView,
    PublicProductListView,
    PublicStoreListView,
)
from catalog.views import (
    CategoryDetailView,
    CategoryListCreateView,
    DashboardSummaryView,
    ProductAttributeDetailView,
    ProductAttributeListCreateView,
    ProductDetailView,
    ProductImageDetailView,
    ProductImageListCreateView,
    ProductListCreateView,
    ProductStoreDetailView,
    ProductStoreListCreateView,
    StoreDetailView,
    StoreListCreateView,
)

app_name = "catalog"

urlpatterns = [
    # Bounded-cost dashboard aggregation (JWT + manage_catalog permission)
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    # Anonymous, read-only customer catalogue (no JWT, no admin permissions)
    path("public/stores/", PublicStoreListView.as_view(), name="public-store-list"),
    path("public/categories/", PublicCategoryListView.as_view(), name="public-category-list"),
    path("public/products/", PublicProductListView.as_view(), name="public-product-list"),
    path(
        "public/products/<int:pk>/",
        PublicProductDetailView.as_view(),
        name="public-product-detail",
    ),
    path("public/images/<int:image_id>/", PublicImageView.as_view(), name="public-image"),
    # Categories
    path("categories/", CategoryListCreateView.as_view(), name="category-list"),
    path("categories/<int:pk>/", CategoryDetailView.as_view(), name="category-detail"),
    # Stores
    path("stores/", StoreListCreateView.as_view(), name="store-list"),
    path("stores/<int:pk>/", StoreDetailView.as_view(), name="store-detail"),
    # Products
    path("products/", ProductListCreateView.as_view(), name="product-list"),
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
    # Product Attributes
    path(
        "products/<int:product_id>/attributes/",
        ProductAttributeListCreateView.as_view(),
        name="product-attribute-list",
    ),
    path(
        "products/<int:product_id>/attributes/<int:attr_id>/",
        ProductAttributeDetailView.as_view(),
        name="product-attribute-detail",
    ),
    # Product Images
    path(
        "products/<int:product_id>/images/",
        ProductImageListCreateView.as_view(),
        name="product-image-list",
    ),
    path(
        "products/<int:product_id>/images/<int:image_id>/",
        ProductImageDetailView.as_view(),
        name="product-image-detail",
    ),
    # Product-Store Associations
    path(
        "products/<int:product_id>/stores/",
        ProductStoreListCreateView.as_view(),
        name="product-store-list",
    ),
    path(
        "products/<int:product_id>/stores/<int:assoc_id>/",
        ProductStoreDetailView.as_view(),
        name="product-store-detail",
    ),
]
