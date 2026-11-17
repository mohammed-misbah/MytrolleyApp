"""Reusable business-permission checks.

Django's ``is_staff`` only controls admin-site access; business operations use
explicit permission codenames. A view sets ``permission_required`` to the
codename it needs.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from accounts.roles import user_has_business_permission


class HasBusinessPermission(BasePermission):
    """Allow only active authenticated users with the view's permission."""

    message = "You do not have permission to perform this action."

    def has_permission(self, request: Request, view: APIView) -> bool:
        required = getattr(view, "permission_required", "")
        if not required or not request.user or not request.user.is_authenticated:
            return False
        return user_has_business_permission(request.user, required)
