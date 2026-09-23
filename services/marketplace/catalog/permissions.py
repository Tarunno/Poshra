from rest_framework import permissions
from rest_framework.request import Request

from accounts.identity import current_user
from accounts.models import Role

__all__ = ["ReadOnlyOrArtisanOwner", "current_user"]


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
