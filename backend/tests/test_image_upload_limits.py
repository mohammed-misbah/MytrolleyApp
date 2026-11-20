"""Product image per-file size limits (1 MB) and format validation."""

from __future__ import annotations

from io import BytesIO

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from catalog.models import Category, Product, ProductImage
from catalog.serializers import ProductImageWriteSerializer
from tests.conftest import access_token, auth_header, login, make_user

MB = 1_048_576


def _png(target_size: int, *, name: str = "pic.png") -> SimpleUploadedFile:
    """Build a valid PNG padded with trailing bytes to the requested size."""
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "green").save(buffer, format="PNG")
    data = buffer.getvalue()
    assert len(data) < target_size
    data += b"\x00" * (target_size - len(data))
    return SimpleUploadedFile(name, data, content_type="image/png")


def test_settings_limits_are_one_megabyte_per_image() -> None:
    assert settings.PRODUCT_IMAGE_MAX_BYTES == MB
    assert settings.PRODUCT_IMAGE_MAX_COUNT == 10
    assert settings.DATA_UPLOAD_MAX_NUMBER_FILES == 10
    assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE > 10 * MB


@pytest.mark.parametrize("size", [200 * 1024, 512 * 1024, MB])
def test_images_up_to_one_megabyte_are_accepted(size: int) -> None:
    serializer = ProductImageWriteSerializer(data={"image": _png(size)})
    assert serializer.is_valid(), serializer.errors


def test_image_larger_than_one_megabyte_is_rejected() -> None:
    serializer = ProductImageWriteSerializer(data={"image": _png(MB + 1)})
    assert not serializer.is_valid()
    assert serializer.errors["image"] == ["File exceeds the 1 MB limit."]


def test_invalid_image_format_is_still_rejected() -> None:
    upload = SimpleUploadedFile("bad.txt", b"not an image", content_type="text/plain")
    serializer = ProductImageWriteSerializer(data={"image": upload})
    assert not serializer.is_valid()
    assert "image" in serializer.errors


def test_eleventh_image_is_rejected(db, client) -> None:
    make_user("image_admin", role="Administrator", is_staff=True)
    token = access_token(login(client, "image_admin", "Correct-Horse-42!"))
    category = Category.objects.create(name="Image Limit", slug="image-limit")
    product = Product.objects.create(
        name="Limited Product", slug="limited-product", category=category
    )
    for index in range(10):
        ProductImage.objects.create(
            product=product,
            image=f"products/{product.pk}/images/{index}.png",
            is_primary=index == 0,
        )

    response = client.post(
        f"/api/v1/products/{product.pk}/images/",
        {"image": _png(1024, name="eleventh.png")},
        **auth_header(token),
    )
    assert response.status_code == 400
    assert "at most 10 images" in response.json()["error"]["message"]
    assert product.images.count() == 10
