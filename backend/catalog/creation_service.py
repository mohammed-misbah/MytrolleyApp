"""Atomic creation of a product together with its images, attributes and stores.

Every input is validated before any row is written. Database work happens in a
single transaction; any storage objects written before a failure are removed so
a rejected request never leaves partial data behind.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from rest_framework.exceptions import ValidationError

from catalog.models import Product, ProductImage
from catalog.serializers import (
    ProductAttributeWriteSerializer,
    ProductImageWriteSerializer,
    ProductStoreWriteSerializer,
    ProductWriteSerializer,
)

_logger = logging.getLogger("mytrolley.catalog.creation")


def _scalar(raw: Any) -> Any:
    """Unwrap a single-element list produced by multipart QueryDict values."""
    if isinstance(raw, list) and len(raw) == 1:
        return raw[0]
    return raw


def _parse_json_list(raw: Any, field: str) -> list[dict[str, Any]]:
    raw = _scalar(raw)
    if raw in (None, "", []):
        return []
    if isinstance(raw, list):
        items = raw
    else:
        try:
            items = json.loads(str(raw))
        except (TypeError, ValueError) as exc:
            raise ValidationError({field: "Enter a valid JSON list."}) from exc
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValidationError({field: "Expected a list of objects."})
    return items


def create_product_with_relations(data: dict[str, Any], files: list[UploadedFile]) -> Product:
    """Validate the whole payload, then create all related rows atomically."""
    product_data = {
        key: _scalar(data.get(key)) for key in ("name", "description", "category_id", "is_active")
    }
    product_data = {key: value for key, value in product_data.items() if value is not None}
    product_serializer = ProductWriteSerializer(data=product_data)

    attribute_items = _parse_json_list(data.get("attributes"), "attributes")
    store_items = _parse_json_list(data.get("stores"), "stores")

    attribute_serializers = [
        ProductAttributeWriteSerializer(data=item, context={"product": None})
        for item in attribute_items
    ]
    store_serializers = [ProductStoreWriteSerializer(data=item) for item in store_items]
    image_serializers = [ProductImageWriteSerializer(data={"image": file}) for file in files]

    # Validate everything before any database or storage write.
    errors: dict[str, Any] = {}
    for name, serializer in (
        ("product", product_serializer),
        *[(f"attributes[{index}]", s) for index, s in enumerate(attribute_serializers)],
        *[(f"stores[{index}]", s) for index, s in enumerate(store_serializers)],
        *[(f"images[{index}]", s) for index, s in enumerate(image_serializers)],
    ):
        if not serializer.is_valid():
            errors[name] = serializer.errors

    if len(files) > settings.PRODUCT_IMAGE_MAX_COUNT:
        errors["images"] = [f"You can upload at most {settings.PRODUCT_IMAGE_MAX_COUNT} images."]

    seen_names = set()
    for index, item in enumerate(attribute_items):
        name = str(item.get("name", "")).strip().lower()
        if name and name in seen_names:
            errors[f"attributes[{index}]"] = {"name": ["Attribute names must be unique."]}
        seen_names.add(name)

    seen_stores = set()
    for index, item in enumerate(store_items):
        store_id = item.get("store_id")
        if store_id is not None and store_id in seen_stores:
            errors[f"stores[{index}]"] = {"store_id": ["A store can only be added once."]}
        seen_stores.add(store_id)

    if errors:
        raise ValidationError(errors)

    stored_names: list[str] = []
    try:
        from django.db import transaction

        with transaction.atomic():
            product: Product = product_serializer.save()
            for serializer in attribute_serializers:
                serializer.save(product=product)
            for serializer in store_serializers:
                serializer.save(product=product)
            for index, serializer in enumerate(image_serializers):
                image: ProductImage = serializer.save(product=product, is_primary=index == 0)
                stored_names.append(image.image.name)
            return product
    except Exception:
        from catalog.image_storage import delete_stored_image

        for name in stored_names:
            delete_stored_image(name)
        raise
