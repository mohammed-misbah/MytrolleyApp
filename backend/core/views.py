"""Public, minimal operational health endpoints."""

from __future__ import annotations

from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.health import database_is_ready


def _health_response(payload: dict[str, str], status_code: int) -> Response:
    response = Response(payload, status=status_code)
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@method_decorator(never_cache, name="dispatch")
class LivenessView(APIView):
    """Process liveness that intentionally does not touch the database."""

    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Health"],
        auth=[],
        summary="Liveness probe",
        description=(
            "Returns 200 while the Django process can serve requests. This "
            "endpoint does not query PostgreSQL."
        ),
        responses={
            200: {
                "type": "object",
                "properties": {"status": {"type": "string", "example": "ok"}},
            }
        },
        examples=[
            OpenApiExample("Live", value={"status": "ok"}, response_only=True),
        ],
    )
    def get(self, request: Request) -> Response:
        return _health_response({"status": "ok"}, status.HTTP_200_OK)


@method_decorator(never_cache, name="dispatch")
class ReadinessView(APIView):
    """Readiness that performs a bounded PostgreSQL query."""

    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Health"],
        auth=[],
        summary="Readiness probe",
        description=(
            "Executes `SELECT 1` against PostgreSQL with a bounded statement "
            "timeout. Returns 503 and a generic body when the database is "
            "unavailable. Responses are never cacheable."
        ),
        responses={
            200: {
                "type": "object",
                "properties": {"status": {"type": "string", "example": "ready"}},
            },
            503: {
                "type": "object",
                "properties": {"status": {"type": "string", "example": "unavailable"}},
            },
        },
        examples=[
            OpenApiExample("Ready", value={"status": "ready"}, response_only=True),
            OpenApiExample(
                "Unavailable",
                value={"status": "unavailable"},
                response_only=True,
                status_codes=["503"],
            ),
        ],
    )
    def get(self, request: Request) -> Response:
        if database_is_ready():
            return _health_response({"status": "ready"}, status.HTTP_200_OK)
        return _health_response(
            {"status": "unavailable"},
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
