"""Authentication endpoints: CSRF bootstrap, login, logout and current user."""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token, rotate_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import (
    CsrfBootstrapSerializer,
    LoginSerializer,
    UserSerializer,
)
from accounts.throttling import (
    check_login_throttle,
    clear_login_throttle,
    record_login_failure,
)
from core.exceptions import InvalidCredentials, LoginRateLimited
from core.schema import CSRF_HEADER_PARAMETER, ErrorEnvelopeSerializer
from core.security import get_client_ip

_auth_logger = logging.getLogger("mytrolley.auth")


def _no_store(response: Response) -> Response:
    response["Cache-Control"] = "no-store"
    return response


def _auth_payload(user: Any, request: Request) -> dict[str, Any]:
    return UserSerializer(user, context={"request": request}).data


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfBootstrapView(APIView):
    """Issue the CSRF cookie/token needed before an anonymous login POST."""

    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        auth=[],
        summary="Bootstrap CSRF token",
        description=(
            "Sets the `csrftoken` cookie and returns a masked CSRF token. The "
            "returned token and the cookie value are both accepted in "
            "`X-CSRFToken`; they are not expected to be identical. Call this "
            "before login and again after login/logout because those "
            "operations rotate the token."
        ),
        responses={200: CsrfBootstrapSerializer},
        examples=[
            OpenApiExample(
                "CSRF bootstrap",
                value={"csrfToken": "masked-csrf-token"},
                response_only=True,
            )
        ],
    )
    def get(self, request: Request) -> Response:
        token = get_token(request)
        return _no_store(Response({"csrfToken": token}))


class LoginView(APIView):
    """Session login with explicit CSRF enforcement for anonymous callers."""

    # SessionAuthentication does not enforce CSRF for anonymous requests, so
    # the POST method is explicitly wrapped with Django's csrf_protect.
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        auth=[],
        summary="Log in",
        description=(
            "Validates credentials, rotates the session ID and CSRF token, and "
            "returns the current user. Failures are generic regardless of "
            "whether the account exists or is inactive. Repeated failures "
            "return 429 with Retry-After. Requires the csrftoken cookie and "
            "matching X-CSRFToken header."
        ),
        request=LoginSerializer,
        parameters=[CSRF_HEADER_PARAMETER],
        responses={
            200: UserSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            429: ErrorEnvelopeSerializer,
        },
        examples=[
            OpenApiExample(
                "Login request",
                value={
                    "username": "administrator",
                    "password": "use-your-own-password",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Authenticated user",
                value={
                    "id": 1,
                    "username": "administrator",
                    "email": "admin@example.test",
                    "first_name": "",
                    "last_name": "",
                    "is_staff": True,
                    "roles": ["Administrator"],
                    "permissions": [
                        "accounts.manage_catalog",
                        "accounts.manage_users",
                    ],
                },
                response_only=True,
            ),
        ],
    )
    @method_decorator(csrf_protect)
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username: str = serializer.validated_data["username"]
        password: str = serializer.validated_data["password"]
        client_ip = get_client_ip(request)

        decision = check_login_throttle(username, client_ip)
        if not decision.allowed:
            _auth_logger.warning(
                "auth.login.rate_limited",
                extra={
                    "event": "auth.login.rate_limited",
                    "retry_after": decision.retry_after_seconds,
                },
            )
            raise LoginRateLimited(decision.retry_after_seconds)

        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active:
            record_login_failure(username, client_ip)
            _auth_logger.warning(
                "auth.login.failed",
                extra={"event": "auth.login.failed"},
            )
            raise InvalidCredentials()

        clear_login_throttle(username, client_ip)
        login(request, user)
        _auth_logger.info(
            "auth.login.succeeded",
            extra={"event": "auth.login.succeeded", "user_id": user.pk},
        )
        return _no_store(Response(_auth_payload(user, request)))


class LogoutView(APIView):
    """Invalidate the session; POST only and CSRF protected by session auth."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Authentication"],
        summary="Log out",
        description=(
            "Flushes the server-side session, rotates the CSRF token and "
            "returns 204. The client must re-fetch the CSRF bootstrap before "
            "logging in again. Requires X-CSRFToken for the authenticated "
            "session."
        ),
        parameters=[CSRF_HEADER_PARAMETER],
        request=None,
        responses={
            204: None,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        user_id = request.user.pk
        logout(request)
        rotate_token(request)
        _auth_logger.info(
            "auth.logout.succeeded",
            extra={"event": "auth.logout.succeeded", "user_id": user_id},
        )
        return _no_store(Response(status=status.HTTP_204_NO_CONTENT))


class MeView(APIView):
    """Return only the authenticated user's own safe account fields."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Authentication"],
        summary="Current authenticated user",
        description=(
            "Returns the caller's safe profile, role names and business "
            "permissions. No user list is exposed."
        ),
        responses={200: UserSerializer, 401: ErrorEnvelopeSerializer},
    )
    def get(self, request: Request) -> Response:
        return _no_store(Response(_auth_payload(request.user, request)))
