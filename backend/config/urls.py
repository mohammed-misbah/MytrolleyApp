"""Root URL configuration for the MyTrolley API."""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.urls.resolvers import URLPattern, URLResolver
from rest_framework.permissions import IsAdminUser

from core.docs import ApiDocsView, ApiSchemaView

urlpatterns: list[URLPattern | URLResolver] = [
    path("api/v1/health/", include("core.urls")),
    path("api/v1/auth/", include("accounts.urls")),
]

if settings.ENABLE_API_DOCS:
    # Documentation is staff-only in every environment. Production leaves it
    # disabled unless explicitly enabled and network-restricted.
    urlpatterns += [
        path(
            "api/v1/schema/",
            ApiSchemaView.as_view(permission_classes=[IsAdminUser]),
            name="openapi-schema",
        ),
        path(
            "api/v1/docs/",
            ApiDocsView.as_view(
                url_name="openapi-schema",
                permission_classes=[IsAdminUser],
            ),
            name="swagger-ui",
        ),
    ]

urlpatterns += [
    path(settings.ADMIN_URL, admin.site.urls),
]

handler400 = "config.views.bad_request"
handler403 = "config.views.permission_denied"
handler404 = "config.views.page_not_found"
handler500 = "config.views.server_error"
