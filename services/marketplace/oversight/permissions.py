"""Who may look across the whole marketplace.

The role is read from the record rather than from the header the gateway sets.
Pahara trusts that header because it has no database to ask; this service has
one, and a role changed a minute ago should take effect now rather than when
somebody's token next happens to be reissued.
"""

from __future__ import annotations

from rest_framework import permissions
from rest_framework.request import Request

from accounts.identity import current_user
from accounts.models import Role


class IsAdmin(permissions.BasePermission):
    message = "This is for administrators."

    def has_permission(self, request: Request, view) -> bool:
        user = current_user(request)
        # Kept on the request so a view does not fetch the same row again.
        request.poshra_user = user
        return user is not None and user.role == Role.ADMIN
