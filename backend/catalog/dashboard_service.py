"""Bounded-cost aggregation for the dashboard summary endpoint.

Every function here issues a fixed number of SQL queries regardless of the
catalogue size. The previous approach fetched whole product pages in Python to
count zero-quantity store associations; that grew linearly with the catalogue.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.request import Request

from catalog.models import Category, Product, ProductStore, Store
from catalog.serializers import ProductListSerializer

RECENT_PRODUCT_LIMIT = 5
CHART_DAYS = 30


def _daily_creation_series() -> list[dict[str, Any]]:
    """Real creations per calendar day for the trailing CHART_DAYS window."""
    end = timezone.localdate()
    start = end - timedelta(days=CHART_DAYS - 1)
    rows = (
        Product.objects.filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
    )
    counts = {row["day"]: row["count"] for row in rows}
    return [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "count": counts.get(start + timedelta(days=index), 0),
        }
        for index in range(CHART_DAYS)
    ]


def build_dashboard_summary(request: Request) -> dict[str, Any]:
    """Return dashboard metrics, recent products and per-store availability."""
    product_totals = Product.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
    )
    category_count = Category.objects.count()
    stores = list(Store.objects.order_by("name"))

    # "Available" keeps its established rule: available association, not deleted.
    available_rows = (
        ProductStore.objects.filter(
            is_available=True,
            product__deleted_at__isnull=True,
        )
        .values("store_id")
        .annotate(available=Count("product_id", distinct=True))
    )
    store_stats = {
        row["store_id"]: {"available": row["available"], "out_of_stock": 0}
        for row in available_rows
    }

    # Out of stock is independent: store-specific quantity == 0, unique live
    # products, regardless of the availability flag, product status or inactive
    # stores. Soft-deleted products are excluded.
    zero_rows = (
        ProductStore.objects.filter(
            quantity=0,
            product__deleted_at__isnull=True,
        )
        .values("store_id")
        .annotate(out_of_stock=Count("product_id", distinct=True))
    )
    for row in zero_rows:
        stats = store_stats.setdefault(row["store_id"], {"available": 0, "out_of_stock": 0})
        stats["out_of_stock"] = row["out_of_stock"]

    recent_queryset = (
        Product.objects.select_related("category")
        .prefetch_related("images", "store_associations__store")
        .order_by("-created_at")[:RECENT_PRODUCT_LIMIT]
    )
    recent = ProductListSerializer(recent_queryset, many=True, context={"request": request}).data

    availability: list[dict[str, Any]] = []
    for store in stores:
        stats = store_stats.get(store.id, {})
        availability.append(
            {
                "id": store.id,
                "name": store.name,
                "code": store.code,
                "description": store.description,
                "address": store.address,
                "is_active": store.is_active,
                "created_at": store.created_at.isoformat() if store.created_at else None,
                "updated_at": store.updated_at.isoformat() if store.updated_at else None,
                "product_count": stats.get("available", 0),
                "out_of_stock": stats.get("out_of_stock", 0),
            }
        )

    return {
        "products": {
            "total": product_totals["total"],
            "active": product_totals["active"],
            "inactive": product_totals["inactive"],
        },
        "categories": category_count,
        "stores": len(stores),
        "recent_products": list(recent),
        "creation_series": _daily_creation_series(),
        "store_availability": availability,
    }
