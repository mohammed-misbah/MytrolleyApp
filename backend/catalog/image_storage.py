"""Storage-agnostic helpers for product image object lifecycle.

All operations use Django's active storage backend so the same code works with
local files during development and private DigitalOcean Spaces objects in
production. Object deletion is deferred until after the database transaction
commits so a failed request never destroys a still-referenced image.
"""

from __future__ import annotations

import logging

from django.core.files.storage import default_storage
from django.db import transaction

_logger = logging.getLogger("mytrolley.catalog.images")


def delete_stored_image(name: str | None) -> None:
    """Delete one stored object by name. Missing objects are not an error."""
    if not name:
        return
    try:
        if default_storage.exists(name):
            default_storage.delete(name)
    except Exception:  # pragma: no cover - cloud failures must not break the request
        _logger.exception("catalog.image.delete_failed")


def delete_stored_image_after_commit(name: str | None) -> None:
    """Schedule object deletion only after the DB transaction commits."""
    if not name:
        return
    transaction.on_commit(lambda: delete_stored_image(name))
