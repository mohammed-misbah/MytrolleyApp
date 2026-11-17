"""Test-only URLconf additions for permission and unhandled-error coverage."""

from __future__ import annotations

from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasBusinessPermission
from config.urls import urlpatterns as base_urlpatterns


class ManageUsersView(APIView):
    """Representative future management endpoint."""

    permission_classes = [HasBusinessPermission]
    permission_required = "accounts.manage_users"

    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class ExplodingView(APIView):
    """Raise an unexpected error to verify generic 500 handling."""

    permission_classes = [AllowAny]
    authentication_classes: list[type] = []

    def get(self, request: Request) -> Response:
        raise RuntimeError("boom")


urlpatterns = base_urlpatterns + [
    path("test-only/manage-users/", ManageUsersView.as_view()),
    path("test-only/explode/", ExplodingView.as_view()),
]
