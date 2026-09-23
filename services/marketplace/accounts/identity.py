"""Who is making this request.

Identity normally arrives as a header that the gateway sets after verifying
the token signature, so services never parse tokens. The header is trusted
only because the network admits gateway traffic alone, and because the gateway
strips any client-supplied copy.

The cookie fallback exists for running a service directly, without a gateway
in front. It is switched off in the cluster: leaving it on would mean a second
token-validation path that could drift from the gateway's.
"""

from __future__ import annotations

from django.conf import settings
from jwt import PyJWTError

from accounts.models import User
from accounts.tokens import decode_access_token

USER_ID_HEADER = "X-User-Id"
ROLE_HEADER = "X-User-Role"


def current_user_id(request) -> str | None:
    """The caller's id, or None when the request is anonymous."""
    if settings.AUTH_TRUST_GATEWAY_HEADER:
        user_id = request.headers.get(USER_ID_HEADER)
        if user_id:
            return user_id

    if not settings.AUTH_COOKIE_FALLBACK:
        return None

    token = request.COOKIES.get(settings.ACCESS_COOKIE_NAME)
    if not token:
        return None
    try:
        return decode_access_token(token)["sub"]
    except PyJWTError:
        return None


def current_user(request) -> User | None:
    user_id = current_user_id(request)
    if not user_id:
        return None
    return User.objects.filter(id=user_id, is_active=True).first()
