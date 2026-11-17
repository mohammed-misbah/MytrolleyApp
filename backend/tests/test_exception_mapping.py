"""Direct coverage of the central exception-to-envelope mapping."""

from __future__ import annotations

import pytest
from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
)
from django.core.exceptions import RequestDataTooBig, SuspiciousOperation
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAcceptable,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from core.errors import normalize_validation_errors
from core.exception_handler import api_exception_handler
from core.exceptions import InvalidCredentials, LoginRateLimited, PayloadTooLarge


def _dispatch(exc: Exception):
    request = Request(APIRequestFactory().get("/api/v1/example/"))
    return api_exception_handler(exc, {"request": request, "view": None})


@pytest.mark.parametrize(
    ("exception", "expected_code", "expected_status"),
    [
        (NotAcceptable(), "NOT_ACCEPTABLE", status.HTTP_406_NOT_ACCEPTABLE),
        (AuthenticationFailed(), "AUTHENTICATION_FAILED", status.HTTP_401_UNAUTHORIZED),
        (NotAuthenticated(), "UNAUTHENTICATED", status.HTTP_401_UNAUTHORIZED),
        (PermissionDenied(), "FORBIDDEN", status.HTTP_403_FORBIDDEN),
        (NotFound(), "NOT_FOUND", status.HTTP_404_NOT_FOUND),
        (MethodNotAllowed("GET"), "METHOD_NOT_ALLOWED", status.HTTP_405_METHOD_NOT_ALLOWED),
        (Http404(), "NOT_FOUND", status.HTTP_404_NOT_FOUND),
        (DjangoPermissionDenied(), "FORBIDDEN", status.HTTP_403_FORBIDDEN),
        (RequestDataTooBig(), "PAYLOAD_TOO_LARGE", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE),
        (SuspiciousOperation(), "BAD_REQUEST", status.HTTP_400_BAD_REQUEST),
        (UnsupportedMediaType("text/plain"), "UNSUPPORTED_MEDIA_TYPE", 415),
        (PayloadTooLarge(), "PAYLOAD_TOO_LARGE", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE),
        (APIException(), "API_ERROR", status.HTTP_500_INTERNAL_SERVER_ERROR),
    ],
)
def test_exception_mapping_is_stable(
    exception: Exception,
    expected_code: str,
    expected_status: int,
) -> None:
    response = _dispatch(exception)

    assert response is not None
    assert response.status_code == expected_status
    assert response.data["error"]["code"] == expected_code
    assert set(response.data["error"]) == {"code", "message", "fields", "request_id"}


def test_throttle_headers_are_preserved() -> None:
    throttled = _dispatch(Throttled(wait=7))
    limited = _dispatch(LoginRateLimited(retry_after_seconds=30))

    assert throttled is not None and limited is not None
    assert throttled["Retry-After"] == "7"
    assert limited["Retry-After"] == "30"
    assert limited.data["error"]["code"] == "RATE_LIMITED"


def test_invalid_credentials_keep_generic_message_and_challenge() -> None:
    response = _dispatch(InvalidCredentials())

    assert response is not None
    assert response.status_code == 401
    assert response.data["error"]["message"] == "Invalid username or password."
    assert response["WWW-Authenticate"] == "Session"


def test_validation_errors_are_flattened_with_dotted_keys() -> None:
    response = _dispatch(
        ValidationError(
            {
                "username": ["This field is required."],
                "profile": {"email": ["Enter a valid email address."]},
                "non_field_errors": ["Passwords do not match."],
            }
        )
    )

    assert response is not None
    fields = response.data["error"]["fields"]
    assert fields["username"] == ["This field is required."]
    assert fields["profile.email"] == ["Enter a valid email address."]
    assert fields["non_field_errors"] == ["Passwords do not match."]


def test_validation_normalizer_handles_scalars_and_empty_lists() -> None:
    assert normalize_validation_errors({"field": []}) == {}
    assert normalize_validation_errors({"field": "single message"}) == {"field": ["single message"]}
