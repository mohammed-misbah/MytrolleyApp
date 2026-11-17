"""Authentication URL routes, mounted under /api/v1/auth/."""

from __future__ import annotations

from django.urls import path

from accounts.views import CsrfBootstrapView, LoginView, LogoutView, MeView

app_name = "accounts"

urlpatterns = [
    path("csrf/", CsrfBootstrapView.as_view(), name="csrf"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
