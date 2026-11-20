"""Controlled concurrent-user HTTP benchmark against an isolated local server.

Usage:
    $env:DB_NAME="mytrolley_bench"
    python manage.py runserver 127.0.0.1:8001 --noreload   # separate shell
    python benchmarks/concurrent_benchmark.py --base http://127.0.0.1:8001 \
        --products 1000 --seed --levels 1,5,10,20 --requests 120
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, cast

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")

from django.conf import settings  # noqa: E402

if "bench" not in str(settings.DATABASES["default"]["NAME"]).lower():
    raise SystemExit("REFUSING: DB_NAME must be an isolated benchmark database")

from benchmark_api import seed  # noqa: E402

from catalog.models import Product  # noqa: E402

LOCAL = threading.local()


def session() -> requests.Session:
    if not getattr(LOCAL, "session", None):
        LOCAL.session = requests.Session()
    return cast(requests.Session, LOCAL.session)


def login(base: str) -> str:
    response = requests.post(
        f"{base}/api/v1/auth/login/",
        json={"username": "bench_admin", "password": "Benchmark-Pass-42!"},
        timeout=10,
    )
    response.raise_for_status()
    return str(response.json()["access"])


def once(base: str, path: str, token: str, timeout: float) -> tuple[float, int]:
    start = time.perf_counter()
    try:
        response = session().get(
            base + path,
            headers={"Authorization": f"Bearer {token}"}
            if not path.startswith("/api/v1/public/")
            else {},
            timeout=timeout,
        )
        status = response.status_code
    except requests.RequestException:
        status = 0
    return (time.perf_counter() - start) * 1000, status


def run_level(base: str, path: str, token: str, users: int, total: int) -> dict[str, Any]:
    latencies: list[float] = []
    statuses: list[int] = []
    lock = threading.Lock()

    def worker(count: int) -> None:
        local_times: list[float] = []
        local_status: list[int] = []
        for _ in range(count):
            latency, status = once(base, path, token, timeout=30)
            local_times.append(latency)
            local_status.append(status)
        with lock:
            latencies.extend(local_times)
            statuses.extend(local_status)

    per_thread = [total // users + (1 if i < total % users else 0) for i in range(users)]
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=users) as pool:
        futures = [pool.submit(worker, count) for count in per_thread if count]
        for future in as_completed(futures):
            future.result()
    wall = time.perf_counter() - start

    latencies.sort()
    return {
        "users": users,
        "requests": len(latencies),
        "rps": round(len(latencies) / wall, 2),
        "median_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))], 2),
        "max_ms": round(latencies[-1], 2),
        "errors": sum(1 for status in statuses if status != 200),
        "error_rate": round(100 * sum(1 for s in statuses if s != 200) / len(statuses), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8001")
    parser.add_argument("--products", type=int, default=1000)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--levels", default="1,5,10,20")
    parser.add_argument("--requests", type=int, default=120)
    parser.add_argument("--label", default="concurrent")
    args = parser.parse_args()

    if args.seed:
        seed(args.products)
    token = login(args.base)

    first_product = Product.objects.order_by("pk").first()
    detail_id = first_product.pk if first_product else 1
    endpoints = {
        "dashboard_summary": "/api/v1/dashboard/summary/",
        "product_list": "/api/v1/products/?page=1&page_size=10",
        "product_detail": f"/api/v1/products/{detail_id}/",
        "public_product_list": "/api/v1/public/products/?page=1&page_size=10",
    }
    results: dict[str, Any] = {"label": args.label, "products": args.products, "endpoints": {}}
    for name, path in endpoints.items():
        results["endpoints"][name] = []
        for users in (int(u) for u in args.levels.split(",")):
            row = run_level(args.base, path, token, users, args.requests)
            results["endpoints"][name].append(row)
            print(
                f"{name:20s} users={users:2d} med={row['median_ms']:8.2f} p95={row['p95_ms']:8.2f} "
                f"max={row['max_ms']:8.2f} rps={row['rps']:7.2f} err={row['error_rate']:5.2f}%"
            )

    out = Path(__file__).parent / f"results_{args.label}_{args.products}.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"results -> {out}")


if __name__ == "__main__":
    main()
