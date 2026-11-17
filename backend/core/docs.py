"""API documentation views that keep error responses in the JSON contract.

drf-spectacular negotiates OpenAPI/YAML renderers for its own views. Without
this mixin, an authentication or permission failure on the schema endpoint
would carry an ``application/vnd.oai.openapi`` content type while every other
API failure is JSON. The envelope itself is already JSON; only the negotiated
renderer needs correcting.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response


class JsonErrorDocsMixin:
    """Force documentation error responses through the JSON renderer."""

    def finalize_response(
        self,
        request: Request,
        response: Response,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)  # type: ignore[misc]
        if response.status_code >= 400:
            response.accepted_renderer = JSONRenderer()
            response.accepted_media_type = "application/json"
            response.renderer_context = self.get_renderer_context()  # type: ignore[attr-defined]
        return response


class ApiSchemaView(JsonErrorDocsMixin, SpectacularAPIView):
    """OpenAPI schema endpoint with JSON error envelopes."""


class ApiDocsView(JsonErrorDocsMixin, SpectacularSwaggerView):
    """Swagger UI endpoint with JSON error envelopes."""
