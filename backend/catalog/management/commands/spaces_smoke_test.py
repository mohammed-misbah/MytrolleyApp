"""Explicit cloud connectivity smoke test.

Uploads one uniquely named temporary object under ``smoke-tests/``, reads it
back, then deletes only that object. Never run automatically in tests.
"""

from __future__ import annotations

import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Verify Spaces connectivity by writing, reading and deleting one temporary object."

    def handle(self, *args: object, **options: object) -> None:
        name = f"smoke-tests/{uuid.uuid4()}.txt"
        payload = b"mytrolley-spaces-smoke-test"
        try:
            default_storage.save(name, ContentFile(payload))
            with default_storage.open(name, "rb") as handle:
                content = handle.read()
            if content != payload:
                raise CommandError("Smoke test failed: content mismatch.")
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"Smoke test failed: {type(exc).__name__}.") from exc
        finally:
            try:
                if default_storage.exists(name):
                    default_storage.delete(name)
            except Exception:  # pragma: no cover
                self.stdout.write("Warning: could not delete temporary smoke object.")
        self.stdout.write(self.style.SUCCESS(f"Smoke test passed for {name} (object deleted)."))
