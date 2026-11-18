"""drf-spectacular security scheme for the custom JWT authentication class."""

from __future__ import annotations

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionAwareJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Document Bearer JWT authentication in the OpenAPI schema."""

    target_class = "accounts.authentication.SessionAwareJWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Paste only the access token returned by POST /api/v1/auth/login/. "
                "Do not include the word Bearer. Access tokens expire after the "
                "configured lifetime; log in again to obtain a new one."
            ),
        }
