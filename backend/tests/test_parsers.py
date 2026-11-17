"""Boundary behaviour of the size-limited JSON parser."""

from __future__ import annotations

from io import BytesIO

import pytest
from django.test import override_settings
from rest_framework.exceptions import ParseError

from core.exceptions import PayloadTooLarge
from core.parsers import BoundedJSONParser


class _Request:
    def __init__(self, content_length: str | None = None) -> None:
        self.META = {} if content_length is None else {"CONTENT_LENGTH": content_length}


def _parse(payload: bytes, *, content_length: str | None = None):
    return BoundedJSONParser().parse(
        BytesIO(payload),
        parser_context={"request": _Request(content_length)},
    )


@override_settings(MAX_JSON_BODY_BYTES=64)
def test_valid_json_is_parsed() -> None:
    assert _parse(b'{"ok": true}', content_length="13") == {"ok": True}


@override_settings(MAX_JSON_BODY_BYTES=64)
def test_declared_oversized_content_length_is_rejected_early() -> None:
    with pytest.raises(PayloadTooLarge):
        _parse(b"{}", content_length="65")


@override_settings(MAX_JSON_BODY_BYTES=64)
def test_invalid_content_length_is_rejected() -> None:
    with pytest.raises(ParseError):
        _parse(b"{}", content_length="not-a-number")
    with pytest.raises(ParseError):
        _parse(b"{}", content_length="-1")


@override_settings(MAX_JSON_BODY_BYTES=64)
def test_actual_oversized_body_is_rejected_without_content_length() -> None:
    with pytest.raises(PayloadTooLarge):
        _parse(b"{" + b"x" * 64 + b"}")


@override_settings(MAX_JSON_BODY_BYTES=64)
def test_empty_and_non_utf8_bodies_are_parse_errors() -> None:
    with pytest.raises(ParseError):
        _parse(b"   ")
    with pytest.raises(ParseError):
        _parse(b"\xff\xfe")


@override_settings(MAX_JSON_BODY_BYTES=64)
def test_malformed_json_is_a_parse_error() -> None:
    with pytest.raises(ParseError):
        _parse(b'{"unterminated":')
