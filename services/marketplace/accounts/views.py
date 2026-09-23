"""Auth endpoints (DRF class-based views).

Tokens are delivered as cookies, never in the response body:

* the access and refresh cookies are ``HttpOnly``, so page JavaScript cannot
  read them and an XSS cannot steal them;
* the refresh cookie is scoped to the auth path, so it is not sent with every
  request;
* a readable CSRF cookie is echoed back in a header on state-changing calls
  (double-submit), which proves the request came from our own page rather than
  from another site that merely has the browser send cookies.

Rate limiting also lives at the gateway; the throttles here are defence in
depth, so the service stays protected if it is ever reached directly.
"""

from __future__ import annotations

import secrets

from django.conf import settings
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts import services
from accounts.identity import current_user
from accounts.serializers import LoginSerializer, RegisterSerializer, UserSerializer
from accounts.tokens import public_jwk

CSRF_HEADER = "X-CSRF-Token"


def _set_auth_cookies(response: Response, pair: services.TokenPair) -> None:
    response.set_cookie(
        settings.ACCESS_COOKIE_NAME,
        pair.access.value,
        max_age=settings.JWT_ACCESS_TTL_SECONDS,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="Lax",
        path="/",
    )
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        pair.refresh_value,
        max_age=settings.JWT_REFRESH_TTL_SECONDS,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="Strict",
        path=settings.REFRESH_COOKIE_PATH,
    )
    response.set_cookie(
        settings.CSRF_COOKIE_NAME_AUTH,
        secrets.token_urlsafe(24),
        max_age=settings.JWT_REFRESH_TTL_SECONDS,
        httponly=False,  # deliberately readable: the page echoes it in a header
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="Lax",
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH)
    response.delete_cookie(settings.CSRF_COOKIE_NAME_AUTH, path="/")


def _csrf_ok(request: Request) -> bool:
    cookie = request.COOKIES.get(settings.CSRF_COOKIE_NAME_AUTH)
    header = request.headers.get(CSRF_HEADER)
    return bool(cookie) and bool(header) and secrets.compare_digest(cookie, header)


class AuthThrottle(ScopedRateThrottle):
    scope = "auth"


class RegisterView(APIView):
    throttle_classes = [AuthThrottle]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            user = services.register(
                email=data["email"],
                password=data["password"],
                full_name=data.get("full_name", ""),
                role=data["role"],
            )
        except services.AuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    throttle_classes = [AuthThrottle]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            pair = services.login(**serializer.validated_data)
        except services.AuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        response = Response(UserSerializer(pair.refresh.user).data)
        _set_auth_cookies(response, pair)
        return response


class RefreshView(APIView):
    throttle_classes = [AuthThrottle]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        if not _csrf_ok(request):
            return Response({"detail": "CSRF check failed"}, status=status.HTTP_403_FORBIDDEN)

        token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not token:
            return Response({"detail": "No refresh token"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            pair = services.refresh(token)
        except services.AuthError as exc:
            response = Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
            _clear_auth_cookies(response)
            return response

        response = Response(UserSerializer(pair.refresh.user).data)
        _set_auth_cookies(response, pair)
        return response


class LogoutView(APIView):
    def post(self, request: Request) -> Response:
        if not _csrf_ok(request):
            return Response({"detail": "CSRF check failed"}, status=status.HTTP_403_FORBIDDEN)

        token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if token:
            services.logout(token)

        response = Response({"detail": "Signed out"})
        _clear_auth_cookies(response)
        return response


class MeView(APIView):
    """The current user.

    Identity comes from the trusted header the gateway injects after verifying
    the token; this view never parses a token itself.
    """

    def get(self, request: Request) -> Response:
        user = current_user(request)
        if user is None:
            return Response({"detail": "Not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(UserSerializer(user).data)


class JWKSView(APIView):
    """Public keys, so verifiers can check signatures without shared secrets."""

    def get(self, request: Request) -> Response:
        response = Response({"keys": [public_jwk()]})
        response["Cache-Control"] = "public, max-age=300"
        return response
