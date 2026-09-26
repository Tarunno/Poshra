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
import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts import services
from accounts.identity import current_user
from accounts.models import AgentToken
from accounts.serializers import (
    AgentTokenCreateSerializer,
    AgentTokenSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
)
from accounts.tokens import AGENT_TOKEN_TTL_DAYS, issue_agent_token, public_jwk

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


class AgentTokensView(APIView):
    """The shopper's agent tokens: list them, or mint a new one.

    The value is in the response exactly once. Storing it so it could be shown
    again would mean holding a credential that grants a shopper's cart, which
    is the thing this design is trying not to do.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "agent-tokens"

    def get(self, request: Request) -> Response:
        user = current_user(request)
        if user is None:
            return Response({"detail": "Sign in first."}, status=status.HTTP_401_UNAUTHORIZED)
        tokens = AgentToken.objects.filter(user=user)
        return Response({"results": AgentTokenSerializer(tokens, many=True).data})

    def post(self, request: Request) -> Response:
        user = current_user(request)
        if user is None:
            return Response({"detail": "Sign in first."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = AgentTokenCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        record = AgentToken(
            user=user,
            label=serializer.validated_data["label"],
            expires_at=timezone.now() + timedelta(days=AGENT_TOKEN_TTL_DAYS),
        )
        issued = issue_agent_token(user, token_id=str(record.id))
        record.expires_at = issued.expires_at
        record.save()

        return Response(
            {"token": issued.value, **AgentTokenSerializer(record).data},
            status=status.HTTP_201_CREATED,
        )


class AgentTokenView(APIView):
    """Revoke one token. Revoking is keeping the row, not deleting it: the
    shopper should be able to see that a token they worried about is dead."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "agent-tokens"

    def delete(self, request: Request, token_id: str) -> Response:
        user = current_user(request)
        if user is None:
            return Response({"detail": "Sign in first."}, status=status.HTTP_401_UNAUTHORIZED)
        # Scoped to the caller: an id from somebody else's account is a 404,
        # which is also the right answer for an id that never existed.
        record = AgentToken.objects.filter(user=user, pk=token_id).first()
        if record is None:
            return Response({"detail": "No such token."}, status=status.HTTP_404_NOT_FOUND)
        if record.revoked_at is None:
            record.revoked_at = timezone.now()
            record.save(update_fields=["revoked_at"])
        return Response(AgentTokenSerializer(record).data)


class AgentTokenIntrospectView(APIView):
    """Is this token still live?

    Asked by the services that act on a shopper's behalf, because the gateway
    cannot know: it verifies a signature, and a signature stays valid after the
    shopper has revoked the row behind it.

    It answers with a bare yes or no. That is deliberate — the only way to know
    a `jti` is to hold the token it came from, so this tells a caller nothing
    it did not already have, and there is nothing here worth guarding beyond
    what the gateway already guards.
    """

    def post(self, request: Request) -> Response:
        token_id = str(request.data.get("token_id") or "").strip()
        record = AgentToken.objects.filter(pk=token_id).first() if _is_uuid(token_id) else None
        if record is None or not record.is_active:
            return Response({"active": False})

        # Doubles as the "last used" the shopper sees. The caller caches its
        # answer, so this lands about once a minute per token rather than once
        # per tool call.
        AgentToken.objects.filter(pk=record.pk).update(last_used_at=timezone.now())
        return Response({"active": True, "user_id": str(record.user_id)})


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True
