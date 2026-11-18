"""API documentation views that keep error responses in the JSON contract.

drf-spectacular negotiates OpenAPI/YAML renderers for its own views. Without
this mixin, an authentication or permission failure on the schema endpoint
would carry an ``application/vnd.oai.openapi`` content type while every other
API failure is JSON. The envelope itself is already JSON; only the negotiated
renderer needs correcting.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny, BasePermission, IsAdminUser
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response


def docs_permission_classes() -> list[type[BasePermission]]:
    """Return the documentation permission policy for this environment.

    Production always sets ``API_DOCS_PUBLIC`` to false, so the schema and
    Swagger UI remain staff-only there. Development defaults it to true so the
    anonymous login flow can be tested without first using Django admin.
    """
    return [AllowAny] if settings.API_DOCS_PUBLIC else [IsAdminUser]


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
