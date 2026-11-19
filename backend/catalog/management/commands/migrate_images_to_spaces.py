"""Copy existing local product images into the configured object storage.

Safe to re-run: objects that already exist with the same size are skipped.
Local files are never deleted. Use --dry-run first to see what would happen.
"""

from __future__ import annotations

from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError

from catalog.models import ProductImage


class Command(BaseCommand):
    help = "Copy locally stored product images into the active default storage (e.g. Spaces)."

    def add_arguments(self, parser: object) -> None:
        parser.add_argument(  # type: ignore[attr-defined]
            "--dry-run",
            action="store_true",
            help="List planned transfers without writing anything.",
        )

    def handle(self, *args: object, **options: object) -> None:
        dry_run = bool(options.get("dry_run"))
        if (
            not getattr(settings, "STORAGES", {})
            .get("default", {})
            .get("BACKEND", "")
            .startswith("storages.backends.s3")
        ):
            raise CommandError(
                "Default storage is not S3/Spaces. Set USE_SPACES_STORAGE=true first."
            )

        source = FileSystemStorage(location=str(settings.MEDIA_ROOT), base_url="")
        images = list(ProductImage.objects.exclude(image="").order_by("id"))
        copied = skipped = failed = missing = 0

        self.stdout.write(f"Images found: {len(images)}. Dry run: {dry_run}")
        for record in images:
            name = record.image.name
            if not source.exists(name):
                self.stdout.write(f"MISSING  id={record.pk} {name}")
                missing += 1
                continue
            source_size = source.size(name)
            if default_storage.exists(name):
                try:
                    remote_size = default_storage.size(name)
                except Exception:
                    remote_size = -1
                if remote_size == source_size:
                    self.stdout.write(f"SKIP     id={record.pk} {name}")
                    skipped += 1
                    continue
                self.stdout.write(f"CONFLICT id={record.pk} {name} (different size)")
                failed += 1
                continue
            if dry_run:
                self.stdout.write(f"PLAN     id={record.pk} {name} ({source_size} bytes)")
                copied += 1
                continue
            try:
                with source.open(name, "rb") as handle:
                    default_storage.save(name, handle)
                self.stdout.write(f"COPIED   id={record.pk} {name}")
                copied += 1
            except Exception as exc:  # pragma: no cover - cloud failures vary
                self.stdout.write(f"FAILED   id={record.pk} {name}: {type(exc).__name__}")
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Done. "
                f"copied/planned={copied} skipped={skipped} "
                f"missing={missing} failed={failed}."
            )
        )
