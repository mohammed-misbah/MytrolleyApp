"""Health URL routes, mounted under /api/v1/health/."""

from __future__ import annotations

from django.urls import path

from core.views import LivenessView, ReadinessView

app_name = "health"

urlpatterns = [
    path("live/", LivenessView.as_view(), name="live"),
    path("ready/", ReadinessView.as_view(), name="ready"),
]
