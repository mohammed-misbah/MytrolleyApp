"""Automated coverage for storage-agnostic product image handling.

Cloud calls are mocked; no files are uploaded to any real bucket.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from PIL import Image

from catalog.image_storage import delete_stored_image
from catalog.models import Category, Product, ProductImage
from config.env import get_spaces_config
from tests.conftest import access_token, auth_header, login


def _png() -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "green").save(buffer, format="PNG")
    return SimpleUploadedFile("space.png", buffer.getvalue(), content_type="image/png")


def test_local_storage_is_default() -> None:
    backend = settings.STORAGES["default"]["BACKEND"]
    assert backend == "django.core.files.storage.FileSystemStorage"
    assert settings.STORAGES["staticfiles"]["BACKEND"].startswith(
        "django.contrib.staticfiles.storage"
    )


def test_missing_spaces_config_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_SPACES_STORAGE", "true")
    monkeypatch.delenv("SPACES_ACCESS_KEY", raising=False)
    monkeypatch.delenv("SPACES_SECRET_KEY", raising=False)
    with pytest.raises(ImproperlyConfigured, match="SPACES_ACCESS_KEY"):
        get_spaces_config()


def test_valid_spaces_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_SPACES_STORAGE", "true")
    monkeypatch.setenv("SPACES_ACCESS_KEY", "key")
    monkeypatch.setenv("SPACES_SECRET_KEY", "secret")
    config = get_spaces_config()
    assert config["enabled"] is True
    assert config["bucket"] == "mytrolley-product-management-media"
    assert config["endpoint"] == "https://sgp1.digitaloceanspaces.com"


@pytest.mark.django_db
def test_upload_multiple_images_and_replace(client: Client, administrator) -> None:
    headers = auth_header(access_token(login(client, "administrator", "Correct-Horse-42!")))
    category = Category.objects.create(name="Storage Category")
    product = Product.objects.create(name="Storage Product", category=category)
    url = f"/api/v1/products/{product.id}/images/"

    first = client.post(url, {"image": _png(), "alt_text": "first"}, **headers)
    assert first.status_code == 201
    second = client.post(url, {"image": _png(), "alt_text": "second"}, **headers)
    assert second.status_code == 201
    assert product.images.count() == 2

    image_id = first.json()["id"]
    old_name = ProductImage.objects.get(pk=image_id).image.name
    from django.test.client import BOUNDARY, encode_multipart

    body = encode_multipart(BOUNDARY, {"image": _png()})
    with patch("catalog.views.delete_stored_image_after_commit") as remove:
        replacement = client.patch(
            f"{url}{image_id}/",
            data=body,
            content_type=f"multipart/form-data; boundary={BOUNDARY}",
            **headers,
        )
    assert replacement.status_code == 200
    assert ProductImage.objects.get(pk=image_id).image.name != old_name
    remove.assert_called_once_with(old_name)


@pytest.mark.django_db
def test_delete_image_removes_object_after_commit(client: Client, administrator) -> None:
    headers = auth_header(access_token(login(client, "administrator", "Correct-Horse-42!")))
    category = Category.objects.create(name="Delete Image Category")
    product = Product.objects.create(name="Delete Image Product", category=category)
    created = client.post(f"/api/v1/products/{product.id}/images/", {"image": _png()}, **headers)
    image_id = created.json()["id"]
    name = ProductImage.objects.get(pk=image_id).image.name
    with patch("catalog.views.delete_stored_image_after_commit") as remove:
        response = client.delete(f"/api/v1/products/{product.id}/images/{image_id}/", **headers)
    assert response.status_code == 204
    assert not ProductImage.objects.filter(pk=image_id).exists()
    remove.assert_called_once_with(name)


@pytest.mark.django_db
def test_public_image_retrieval_uses_storage_api(client: Client) -> None:
    category = Category.objects.create(name="Public Image Category")
    product = Product.objects.create(name="Public Image Product", category=category)
    store = __import__("catalog.models", fromlist=["Store"]).Store.objects.create(
        name="Image Store", code="IMST"
    )
    __import__("catalog.models", fromlist=["ProductStore"]).ProductStore.objects.create(
        product=product, store=store, price="1", quantity=1
    )
    image = ProductImage.objects.create(product=product, image=_png(), is_primary=True)
    response = client.get(f"/api/v1/public/images/{image.pk}/")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("image/")


@pytest.mark.django_db
def test_delete_stored_image_is_storage_agnostic() -> None:
    with patch("catalog.image_storage.default_storage") as storage:
        storage.exists.return_value = True
        delete_stored_image("products/1/images/x.png")
        storage.delete.assert_called_once_with("products/1/images/x.png")


@pytest.mark.django_db
def test_invalid_image_format_rejected(client: Client, administrator) -> None:
    headers = auth_header(access_token(login(client, "administrator", "Correct-Horse-42!")))
    category = Category.objects.create(name="Invalid Image Category")
    product = Product.objects.create(name="Invalid Image Product", category=category)
    bad = SimpleUploadedFile("bad.txt", b"not an image", content_type="text/plain")
    response = client.post(f"/api/v1/products/{product.id}/images/", {"image": bad}, **headers)
    assert response.status_code == 400
    assert product.images.count() == 0


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "access_key": "test",
                "secret_key": "test",
                "bucket_name": "mytrolley-product-management-media",
                "region_name": "sgp1",
                "endpoint_url": "https://sgp1.digitaloceanspaces.com",
                "default_acl": None,
                "querystring_auth": True,
                "querystring_expire": 300,
                "file_overwrite": False,
            },
        },
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
def test_spaces_storage_configuration_is_applied() -> None:
    from django.core.files.storage import default_storage

    assert default_storage.__class__.__name__ == "S3Storage"
