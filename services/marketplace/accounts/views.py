"""Auth endpoints.

Tokens are delivered as cookies, never in the response body:

* the access and refresh cookies are ``HttpOnly``, so page JavaScript cannot
  read them and an XSS cannot steal them;
* the refresh cookie is scoped to the auth path, so it is not sent with every
  request;
* a readable CSRF cookie is echoed back in a header on state-changing calls
  (double-submit), which proves the request came from our own page rather than
  from another site that merely has the browser send cookies.
"""

from __future__ import annotations

import secrets

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from accounts import services
from accounts.models import Role, User
from accounts.tokens import public_jwk

CSRF_HEADER = "X-CSRF-Token"


def _json_body(request: HttpRequest) -> dict:
    import json

    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return {}


def _set_auth_cookies(response: HttpResponse, pair: services.TokenPair) -> None:
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


def _clear_auth_cookies(response: HttpResponse) -> None:
    response.delete_cookie(settings.ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH)
    response.delete_cookie(settings.CSRF_COOKIE_NAME_AUTH, path="/")


def _user_json(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
    }


def _csrf_ok(request: HttpRequest) -> bool:
    cookie = request.COOKIES.get(settings.CSRF_COOKIE_NAME_AUTH)
    header = request.headers.get(CSRF_HEADER)
    return bool(cookie) and bool(header) and secrets.compare_digest(cookie, header)


@csrf_exempt
@require_POST
def register(request: HttpRequest) -> JsonResponse:
    body = _json_body(request)
    role = body.get("role", Role.BUYER)
    if role not in (Role.BUYER, Role.ARTISAN):
        return JsonResponse({"detail": "role must be buyer or artisan"}, status=400)
    if not body.get("email") or not body.get("password"):
        return JsonResponse({"detail": "email and password are required"}, status=400)

    try:
        user = services.register(
            email=body["email"],
            password=body["password"],
            full_name=body.get("full_name", ""),
            role=role,
        )
    except services.AuthError as exc:
        return JsonResponse({"detail": str(exc)}, status=409)

    return JsonResponse(_user_json(user), status=201)


@csrf_exempt
@require_POST
def login(request: HttpRequest) -> JsonResponse:
    body = _json_body(request)
    try:
        pair = services.login(email=body.get("email", ""), password=body.get("password", ""))
    except services.AuthError as exc:
        return JsonResponse({"detail": str(exc)}, status=401)

    response = JsonResponse(_user_json(pair.refresh.user))
    _set_auth_cookies(response, pair)
    return response


@csrf_exempt
@require_POST
def refresh(request: HttpRequest) -> JsonResponse:
    if not _csrf_ok(request):
        return JsonResponse({"detail": "CSRF check failed"}, status=403)

    token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
    if not token:
        return JsonResponse({"detail": "No refresh token"}, status=401)

    try:
        pair = services.refresh(token)
    except services.AuthError as exc:
        response = JsonResponse({"detail": str(exc)}, status=401)
        _clear_auth_cookies(response)
        return response

    response = JsonResponse(_user_json(pair.refresh.user))
    _set_auth_cookies(response, pair)
    return response


@csrf_exempt
@require_POST
def logout(request: HttpRequest) -> JsonResponse:
    if not _csrf_ok(request):
        return JsonResponse({"detail": "CSRF check failed"}, status=403)

    token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
    if token:
        services.logout(token)

    response = JsonResponse({"detail": "Signed out"})
    _clear_auth_cookies(response)
    return response


@require_GET
def jwks(request: HttpRequest) -> JsonResponse:
    """Public keys, so verifiers can check signatures without shared secrets."""
    response = JsonResponse({"keys": [public_jwk()]})
    response["Cache-Control"] = "public, max-age=300"
    return response
