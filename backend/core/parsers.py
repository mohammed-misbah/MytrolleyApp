"""Bounded JSON parser to enforce request-size limits before deserialization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from django.conf import settings
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser

from core.exceptions import PayloadTooLarge


class BoundedJSONParser(JSONParser):
    """Parse JSON only when the raw body stays within the configured limit."""

    media_type = "application/json"

    def parse(
        self,
        stream: Any,
        media_type: str | None = None,
        parser_context: Mapping[str, Any] | None = None,
    ) -> Any:
        context = parser_context or {}
        request = context.get("request")
        limit = settings.MAX_JSON_BODY_BYTES

        if request is not None:
            raw_length = request.META.get("CONTENT_LENGTH")
            if raw_length:
                try:
                    declared = int(raw_length)
                except (TypeError, ValueError) as exc:
                    raise ParseError("Invalid Content-Length header.") from exc
                if declared < 0:
                    raise ParseError("Invalid Content-Length header.")
                if declared > limit:
                    raise PayloadTooLarge()

        raw_body = stream.read(limit + 1)
        if len(raw_body) > limit:
            raise PayloadTooLarge()
        if not raw_body.strip():
            raise ParseError("Request body is empty.")
        try:
            text = raw_body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParseError("Request body must be valid UTF-8.") from exc
        try:
            return json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            # The parser message is never returned to clients; the central
            # handler maps this to a generic INVALID_JSON response.
            raise ParseError("Request body contains invalid JSON.") from exc
