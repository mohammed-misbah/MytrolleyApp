"""Root URL configuration for the MyTrolley API."""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.urls.resolvers import URLPattern, URLResolver

from core.docs import ApiDocsView, ApiSchemaView, docs_permission_classes

urlpatterns: list[URLPattern | URLResolver] = [
    path("api/v1/health/", include("core.urls")),
    path("api/v1/auth/", include("accounts.urls")),
]

if settings.ENABLE_API_DOCS:
    # Production is staff-only. Development may deliberately expose the docs so
    # the anonymous login flow can be tested from the browser.
    _docs_permissions = docs_permission_classes()
    urlpatterns += [
        path(
            "api/v1/schema/",
            ApiSchemaView.as_view(permission_classes=_docs_permissions),
            name="openapi-schema",
        ),
        path(
            "api/v1/docs/",
            ApiDocsView.as_view(
                url_name="openapi-schema",
                permission_classes=_docs_permissions,
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
