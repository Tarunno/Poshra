from rest_framework import permissions
from rest_framework.request import Request

from accounts.models import Role, User


def current_user(request: Request) -> User | None:
    """The caller, from the identity header the gateway injects.

    Services never parse tokens: the gateway verifies the signature and passes
    a trusted user id on the internal network. Until that plugin exists the
    access cookie is verified here as a fallback.
    """
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        from django.conf import settings
        from jwt import PyJWTError

        from accounts.tokens import decode_access_token

        token = request.COOKIES.get(settings.ACCESS_COOKIE_NAME)
        if not token:
            return None
        try:
            user_id = decode_access_token(token)["sub"]
        except PyJWTError:
            return None
    return User.objects.filter(id=user_id, is_active=True).first()


class ReadOnlyOrArtisanOwner(permissions.BasePermission):
    """Anyone may browse. Only the artisan who owns a listing may change it."""

    message = "Only the artisan who owns this listing can change it."

    def has_permission(self, request: Request, view) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        user = current_user(request)
        request.poshra_user = user
        return user is not None and user.role in (Role.ARTISAN, Role.ADMIN)

    def has_object_permission(self, request: Request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        user = getattr(request, "poshra_user", None) or current_user(request)
        if user is None:
            return False
        if user.role == Role.ADMIN:
            return True
        # Object-level check: a role alone is not authorisation. Without this
        # any artisan could edit any other artisan's listing (BOLA/IDOR).
        return getattr(obj.artisan, "user_id", None) == user.id
