"""JWT authentication endpoints: login, refresh, logout and current user."""

from __future__ import annotations

import logging
import uuid
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import AuthSession
from accounts.serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    LogoutResponseSerializer,
    RefreshRequestSerializer,
    UserSerializer,
)
from accounts.throttling import (
    check_login_throttle,
    check_refresh_throttle,
    clear_login_throttle,
    clear_refresh_throttle,
    record_login_failure,
)
from accounts.tokens import (
    IssuedTokens,
    _revoke_family_outside_transaction,
    create_auth_session,
    revoke_user_sessions,
    rotate_refresh_token,
)
from core.exceptions import (
    InvalidCredentials,
    InvalidRefreshToken,
    LoginRateLimited,
    RefreshReuseDetected,
    SessionRevoked,
)
from core.schema import ErrorEnvelopeSerializer
from core.security import get_client_ip

_auth_logger = logging.getLogger("mytrolley.auth")

# Refresh failures that already carry the public error contract; they are
# re-raised untouched instead of being rewritten as a generic token error.
_REFRESH_PASSTHROUGH = (InvalidRefreshToken, SessionRevoked)

LOGOUT_SUCCESS_MESSAGE = (
    "Logout successful. All active sessions for the current user have been revoked."
)

_REFRESH_COOKIE_NAME = "refresh_token"
_REFRESH_COOKIE_PATH = "/api/v1/auth/"


def _refresh_cookie_attributes() -> dict[str, Any]:
    """Cookie flags shared by the set and clear operations.

    Clearing a cookie only works when path, domain and SameSite match the
    original cookie, so both operations read this single source of truth.
    """
    secure = not settings.DEBUG
    return {
        "httponly": True,
        "secure": secure,
        "samesite": "Lax" if settings.DEBUG else "Strict",
        "path": _REFRESH_COOKIE_PATH,
    }


def _no_store(response: Response) -> Response:
    response["Cache-Control"] = "no-store"
    return response


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Set the refresh token as an HttpOnly cookie with secure defaults."""
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.JWT_REFRESH_TOKEN_LIFETIME_SECONDS,
        **_refresh_cookie_attributes(),
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear the refresh cookie using the attributes it was set with.

    Django's ``delete_cookie`` accepts path, domain and SameSite only; those
    are the attributes the browser matches on. It expires the cookie itself.
    """
    attributes = _refresh_cookie_attributes()
    response.delete_cookie(
        key=_REFRESH_COOKIE_NAME,
        path=attributes["path"],
        samesite=attributes["samesite"],
    )


def _csrf_response(request: HttpRequest) -> HttpResponse:
    """Placeholder callable for ``CsrfViewMiddleware.process_view``.

    It is never routed or returned. The middleware only needs a non-exempt
    view object so it runs its origin and token checks for this request.
    """
    return HttpResponse(status=status.HTTP_204_NO_CONTENT)


_CSRF_MIDDLEWARE = CsrfViewMiddleware(_csrf_response)


def _require_csrf(request: Request) -> None:
    """Enforce CSRF when a state change is authorized by a cookie.

    The refresh token is the only ambient credential the API accepts, so it is
    also the only place where a cross-site request could act on its own. A
    refresh token supplied in the request body is not ambient and does not need
    CSRF; a token read from the HttpOnly cookie does.
    """
    if _CSRF_MIDDLEWARE.process_view(request._request, _csrf_response, (), {}) is not None:
        raise PermissionDenied("CSRF verification failed.")


def _revoke_token_family_from_claim(token: RefreshToken) -> None:
    """Revoke the token family named inside a signature-verified refresh token.

    Tokens minted before the ``fam`` claim existed cannot identify their family;
    those are rejected without touching any other login's sessions.
    """
    family_id = token.get("fam")
    if not isinstance(family_id, str) or not family_id:
        return
    try:
        parsed = uuid.UUID(family_id)
    except ValueError:
        return
    _revoke_family_outside_transaction(
        parsed, timezone.now(), AuthSession.RevokeReason.REFRESH_REUSE
    )


def _user_payload(user: Any, request: Request) -> dict[str, Any]:
    return UserSerializer(user, context={"request": request}).data


def _token_payload(tokens: IssuedTokens) -> dict[str, Any]:
    """Response metadata for a token pair.

    The refresh token itself is never serialized to JSON: browsers receive it
    only as an HttpOnly cookie so page script cannot read or persist it.
    """
    return {
        "access": tokens.access,
        "token_type": "Bearer",
        "expires_in": tokens.access_expires_in,
        "refresh_expires_in": tokens.refresh_expires_in,
    }


@method_decorator(ensure_csrf_cookie, name="dispatch")
class LoginView(APIView):
    """Exchange username/password for a short-lived access token and a refresh token."""

    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        auth=[],
        summary="Log in and obtain access/refresh tokens",
        description=(
            "Validates credentials, rejects inactive accounts, applies the "
            "database-backed login throttle and creates a server-side auth "
            "session. Returns a short-lived access token and the caller's safe "
            "profile. The refresh token is delivered only as an HttpOnly "
            "cookie; it is never included in this JSON response. Send the "
            "access token to protected endpoints as `Authorization: Bearer "
            "<access>`. The response also sets the readable `csrftoken` cookie "
            "that a browser must echo in `X-CSRFToken` when it refreshes from "
            "the cookie. Failures are generic whether the account exists, is "
            "inactive or has the wrong password."
        ),
        request=LoginSerializer,
        responses={
            200: LoginResponseSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            429: ErrorEnvelopeSerializer,
        },
        examples=[
            OpenApiExample(
                "Login request",
                value={
                    "username": "administrator",
                    "password": "password",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Access token and user",
                value={
                    "access": "access-token-placeholder",
                    "token_type": "Bearer",
                    "expires_in": 300,
                    "refresh_expires_in": 86400,
                    "user": {
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
                },
                response_only=True,
            ),
        ],
    )
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
        clear_refresh_throttle(user.pk, client_ip)
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        tokens = create_auth_session(user, request)
        _auth_logger.info(
            "auth.login.succeeded",
            extra={"event": "auth.login.succeeded", "user_id": user.pk},
        )
        response = _no_store(
            Response(
                {
                    **_token_payload(tokens),
                    "user": _user_payload(user, request),
                }
            )
        )
        _set_refresh_cookie(response, tokens.refresh)
        return response


class RefreshView(APIView):
    """Rotate access and refresh tokens using a valid refresh token."""

    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    def get_authenticate_header(self, request: Request) -> str:
        """Keep revoked-session failures at 401 instead of DRF's 403 fallback.

        A view with no authenticator normally downgrades ``AuthenticationFailed``
        to 403. Refresh errors are token failures, so the documented contract is
        401 plus ``WWW-Authenticate: Bearer``.
        """
        return "Bearer"

    @extend_schema(
        tags=["Authentication"],
        auth=[],
        summary="Refresh access token",
        description=(
            "Rotates the access and refresh tokens. Browsers send the HttpOnly "
            "refresh cookie automatically; API clients may send the refresh "
            "token in the request body instead. A cookie-authorized refresh must "
            "also send `X-CSRFToken`. On success a new access token is returned "
            "and the refresh cookie is replaced; the consumed token stops "
            "working and replaying it revokes the whole token family. This "
            "endpoint is intentionally excluded from Swagger UI and is "
            "documented in `docs/frontend-integration.md`."
        ),
        request=RefreshRequestSerializer,
        responses={
            200: LoginResponseSerializer,
            400: ErrorEnvelopeSerializer,
            401: ErrorEnvelopeSerializer,
            403: ErrorEnvelopeSerializer,
            429: ErrorEnvelopeSerializer,
        },
        exclude=True,  # Hidden from public Swagger UI, still fully operational.
    )
    def post(self, request: Request) -> Response:
        serializer = RefreshRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body_token: str | None = serializer.validated_data.get("refresh")
        cookie_token = request.COOKIES.get(_REFRESH_COOKIE_NAME)
        refresh_token_str = body_token or cookie_token
        if not refresh_token_str:
            raise InvalidRefreshToken("Refresh token is required.")

        if not body_token and cookie_token:
            # The cookie is the authority for this request, so it must prove
            # same-site intent. Body tokens are explicit credentials and are
            # not reachable by a cross-site form post.
            _require_csrf(request)

        client_ip = get_client_ip(request)

        try:
            # RefreshToken verifies signature, expiry, issuer, audience and
            # token type. UntypedToken would skip type and claim checks.
            token = RefreshToken(cast(Any, refresh_token_str))
        except TokenError as exc:
            _auth_logger.warning(
                "auth.refresh.malformed",
                extra={"event": "auth.refresh.malformed"},
            )
            raise InvalidRefreshToken() from exc

        user_id = token.get("user_id")
        jti = token.get("jti")

        decision = check_refresh_throttle(user_id, client_ip)
        if not decision.allowed:
            _auth_logger.warning(
                "auth.refresh.rate_limited",
                extra={
                    "event": "auth.refresh.rate_limited",
                    "retry_after": decision.retry_after_seconds,
                },
            )
            raise LoginRateLimited(decision.retry_after_seconds)

        try:
            session = AuthSession.objects.get(refresh_jti=jti)
        except AuthSession.DoesNotExist as exc:
            # The JTI is signed by this API but no session stores it, so the
            # token was consumed by an earlier rotation. Revoke exactly its own
            # family; never another login's family for the same user.
            _revoke_token_family_from_claim(token)
            _auth_logger.warning(
                "auth.refresh.reuse_detected",
                extra={"event": "auth.refresh.reuse_detected", "user_id": user_id},
            )
            raise InvalidRefreshToken() from exc

        try:
            tokens = rotate_refresh_token(session, token, request=request)
        except RefreshReuseDetected as exc:
            # Reuse detected: the token family needs to be fully revoked.
            # This runs in a new transaction after the rotation transaction rolled back.
            _revoke_family_outside_transaction(
                exc.family_id, timezone.now(), AuthSession.RevokeReason.REFRESH_REUSE
            )
            raise
        except _REFRESH_PASSTHROUGH:
            raise
        except Exception as exc:
            _auth_logger.error(
                "auth.refresh.error",
                extra={"event": "auth.refresh.error"},
                exc_info=exc,
            )
            raise InvalidRefreshToken() from exc

        _auth_logger.info(
            "auth.refresh.succeeded",
            extra={"event": "auth.refresh.succeeded", "user_id": session.user_id},
        )
        response = _no_store(
            Response(
                {
                    **_token_payload(tokens),
                    "user": _user_payload(session.user, request),
                }
            )
        )
        _set_refresh_cookie(response, tokens.refresh)
        return response


class LogoutView(APIView):
    """Revoke every login session and token belonging to the caller."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Authentication"],
        summary="Log out all sessions for the current user",
        description=(
            "Requires the access token in the Authorization header. Revokes "
            "every active login session for the authenticated user, so all of "
            "that user's access and refresh tokens stop working immediately. "
            "The refresh cookie is cleared. Other users' sessions are not "
            "affected. No request body is required. The success message below "
            "is a static example of the documented contract, not a response "
            "captured from the server."
        ),
        request=None,
        responses={
            200: LogoutResponseSerializer,
            401: ErrorEnvelopeSerializer,
            500: ErrorEnvelopeSerializer,
        },
        examples=[
            OpenApiExample(
                "Successful logout",
                value={"message": LOGOUT_SUCCESS_MESSAGE},
                response_only=True,
            )
        ],
    )
    def post(self, request: Request) -> Response:
        user_id = cast(int, request.user.pk)
        try:
            revoked = revoke_user_sessions(
                user_id,
                reason=AuthSession.RevokeReason.LOGOUT_ALL,
            )
        except Exception:
            # Fail closed: an authentication failure must never look like a
            # successful logout, and the response must not include the message.
            _auth_logger.exception(
                "auth.logout.failed",
                extra={"event": "auth.logout.failed", "user_id": user_id},
            )
            raise
        _auth_logger.info(
            "auth.logout.succeeded",
            extra={
                "event": "auth.logout.succeeded",
                "user_id": user_id,
                "revoked_sessions": revoked,
            },
        )
        response = _no_store(
            Response({"message": LOGOUT_SUCCESS_MESSAGE}, status=status.HTTP_200_OK)
        )
        _clear_refresh_cookie(response)
        return response


class MeView(APIView):
    """Return only the authenticated user's own safe account fields."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Authentication"],
        summary="Current authenticated user",
        description=(
            "Returns the caller's safe profile, role names and business "
            "permissions. No user list is exposed. Requires a valid access "
            "token and an active server-side session."
        ),
        responses={200: UserSerializer, 401: ErrorEnvelopeSerializer},
    )
    def get(self, request: Request) -> Response:
        return _no_store(Response(_user_payload(request.user, request)))
