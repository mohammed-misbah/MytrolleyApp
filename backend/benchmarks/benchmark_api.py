"""Reproducible local API benchmark for MyTrolleyApp.

Runs ONLY against an explicitly named isolated database (default:
``mytrolley_bench``). Never points at the development/production database.

Usage (from backend/):
    $env:DB_NAME="mytrolley_bench"
    python manage.py migrate --noinput
    python benchmarks/benchmark_api.py --seed --products 1000 --repeat 7
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import django
from django.conf import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from accounts.roles import ROLE_ADMINISTRATOR, seed_roles  # noqa: E402
from catalog.models import Category, Product, ProductAttribute, ProductImage, ProductStore, Store  # noqa: E402

BENCH_DB = "mytrolley_bench"


def guard_database() -> None:
    name = str(settings.DATABASES["default"]["NAME"]).lower()
    if "bench" not in name and "test" not in name:
        raise SystemExit(
            f"REFUSING to benchmark database {name!r}. "
            "Set DB_NAME to an isolated benchmark database (e.g. mytrolley_bench)."
        )


def seed(product_count: int) -> None:
    guard_database()
    User = get_user_model()
    # Isolated benchmark DB only: safe to clear between runs.
    ProductAttribute.objects.all().delete()
    ProductImage.objects.all().delete()
    ProductStore.objects.all().delete()
    Product.all_objects.all().delete()
    Category.objects.all().delete()
    Store.objects.all().delete()
    User.objects.filter(username="bench_admin").delete()

    roles = seed_roles()
    admin = User.objects.create_user(
        username="bench_admin",
        email="bench@example.test",
        password="Benchmark-Pass-42!",
        is_staff=True,
    )
    admin.groups.add(roles[ROLE_ADMINISTRATOR])

    categories = Category.objects.bulk_create(
        [Category(name=f"Benchmark Category {i}", slug=f"benchmark-category-{i}") for i in range(6)]
    )
    stores = Store.objects.bulk_create(
        [Store(name=f"Benchmark Store {i}", code=f"BST{i}") for i in range(3)]
    )

    products: list[Product] = []
    for i in range(product_count):
        products.append(
            Product(
                name=f"Benchmark Product {i:05d}",
                slug=f"benchmark-product-{i:05d}",
                description="Benchmark product description.",
                category=categories[i % len(categories)],
                is_active=i % 11 != 0,
            )
        )
    Product.objects.bulk_create(products, batch_size=1000)
    product_ids = list(Product.objects.values_list("id", flat=True))

    images: list[ProductImage] = []
    associations: list[ProductStore] = []
    attributes: list[ProductAttribute] = []
    for index, pid in enumerate(product_ids):
        images.append(
            ProductImage(
                product_id=pid,
                image=f"products/{pid}/images/{uuid.uuid4()}.png",
                alt_text="Benchmark image",
                display_order=0,
                is_primary=True,
            )
        )
        if index % 3 == 0:
            images.append(
                ProductImage(
                    product_id=pid,
                    image=f"products/{pid}/images/{uuid.uuid4()}.png",
                    alt_text="Benchmark secondary image",
                    display_order=1,
                )
            )
        for store in stores:
            associations.append(
                ProductStore(
                    product_id=pid,
                    store_id=store.id,
                    price=Decimal("12.50"),
                    quantity=0 if index % 10 == 0 else 25,
                    is_available=True,
                )
            )
        attributes.append(ProductAttribute(product_id=pid, name="size", value="M"))
    ProductImage.objects.bulk_create(images, batch_size=1000)
    ProductStore.objects.bulk_create(associations, batch_size=1000)
    ProductAttribute.objects.bulk_create(attributes, batch_size=1000)

    print(
        f"seeded {product_count} products, {len(images)} images, {len(associations)} associations"
    )
    return None


def get_token(client: Client) -> str:
    response = client.post(
        "/api/v1/auth/login/",
        data=json.dumps({"username": "bench_admin", "password": "Benchmark-Pass-42!"}),
        content_type="application/json",
    )
    if response.status_code != 200:
        raise SystemExit(f"login failed: {response.status_code} {response.content[:300]!r}")
    return str(response.json()["access"])


def measure(client: Client, url: str, headers: dict[str, Any], repeat: int) -> dict[str, Any]:
    times: list[float] = []
    queries: list[int] = []
    sql_times: list[float] = []
    sizes: list[int] = []
    statuses: list[int] = []
    for _ in range(repeat):
        with CaptureQueriesContext(connection) as captured:
            start = time.perf_counter()
            response = client.get(url, **headers)
            times.append((time.perf_counter() - start) * 1000)
        statuses.append(response.status_code)
        sizes.append(len(response.content))
        queries.append(len(captured.captured_queries))
        sql_times.append(sum(float(q["time"]) for q in captured.captured_queries) * 1000)
    times.sort()
    return {
        "min_ms": round(times[0], 2),
        "median_ms": round(statistics.median(times), 2),
        "p95_ms": round(times[min(len(times) - 1, int(len(times) * 0.95))], 2),
        "max_ms": round(times[-1], 2),
        "queries": queries[0],
        "query_time_ms": round(sql_times[0], 2),
        "payload_bytes": sizes[0],
        "status": statuses[0],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--products", type=int, default=1000)
    parser.add_argument("--repeat", type=int, default=7)
    parser.add_argument("--label", default="baseline")
    args = parser.parse_args()

    guard_database()
    if args.seed:
        seed(args.products)

    client = Client(enforce_csrf_checks=True)
    token = get_token(client)
    headers: dict[str, Any] = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
    pk = Product.objects.filter(is_active=True).order_by("pk").values_list("pk", flat=True).first()
    cat = Category.objects.order_by("pk").values_list("pk", flat=True).first()
    store = Store.objects.order_by("pk").values_list("pk", flat=True).first()

    endpoints: dict[str, str] = {
        "product_list": "/api/v1/products/?page=1&page_size=10",
        "product_search": "/api/v1/products/?page=1&page_size=10&search=Benchmark",
        "product_category_filter": f"/api/v1/products/?page=1&page_size=10&category={cat}",
        "product_store_filter": f"/api/v1/products/?page=1&page_size=10&store={store}",
        "product_sort": "/api/v1/products/?page=1&page_size=10&ordering=-created_at",
        "product_detail": f"/api/v1/products/{pk}/",
        "dashboard_summary": "/api/v1/dashboard/summary/",
        "categories": "/api/v1/categories/",
        "stores": "/api/v1/stores/",
        "public_product_list": "/api/v1/public/products/?page=1&page_size=10",
        "public_product_detail": f"/api/v1/public/products/{pk}/",
        "public_categories": "/api/v1/public/categories/",
        "public_stores": "/api/v1/public/stores/",
    }

    results = {
        "label": args.label,
        "products_in_db": Product.objects.count(),
        "repeat": args.repeat,
        "endpoints": {},
    }
    for name, url in endpoints.items():
        results["endpoints"][name] = measure(client, url, headers, args.repeat)
        row = results["endpoints"][name]
        print(
            f"{name:26s} med={row['median_ms']:8.2f}ms p95={row['p95_ms']:8.2f}ms "
            f"q={row['queries']:3d} sql={row['query_time_ms']:8.2f}ms "
            f"bytes={row['payload_bytes']:7d} status={row['status']}"
        )

    out = Path(__file__).parent / f"results_{args.label}_{args.products}.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"results -> {out}")


if __name__ == "__main__":
    main()
