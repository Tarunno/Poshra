"""Authentication use cases, kept out of the views so they can be tested directly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import RefreshToken, User
from accounts.tokens import (
    AccessToken,
    generate_refresh_token,
    hash_refresh_token,
    issue_access_token,
)


class AuthError(Exception):
    """Authentication failed. The message is safe to return to the client."""


@dataclass(frozen=True)
class TokenPair:
    access: AccessToken
    refresh_value: str
    refresh: RefreshToken


def _new_refresh_token(user: User, family=None) -> tuple[str, RefreshToken]:
    value = generate_refresh_token()
    record = RefreshToken.objects.create(
        user=user,
        token_hash=hash_refresh_token(value),
        expires_at=timezone.now() + timedelta(seconds=settings.JWT_REFRESH_TTL_SECONDS),
        **({"family": family} if family else {}),
    )
    return value, record


def login(email: str, password: str) -> TokenPair:
    """Verify credentials and start a new token family."""
    user = User.objects.filter(email=email.lower().strip()).first()
    if user is None:
        # Hash anyway so a missing account and a wrong password take the same
        # time; otherwise response timing reveals which emails are registered.
        User().set_password(password)
        raise AuthError("Invalid email or password")
    if not user.check_password(password):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("Account is disabled")

    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    value, record = _new_refresh_token(user)
    return TokenPair(access=issue_access_token(user), refresh_value=value, refresh=record)


def refresh(token_value: str) -> TokenPair:
    """Rotate a refresh token, detecting replay of an already-used token.

    Note the transaction boundary: revoking a family after detecting reuse must
    be committed *before* the error is raised. Raising inside the transaction
    would roll the revocation back and leave the stolen session alive.
    """
    with transaction.atomic():
        record = (
            RefreshToken.objects.select_for_update()
            .select_related("user")
            .filter(token_hash=hash_refresh_token(token_value))
            .first()
        )
        if record is None:
            raise AuthError("Invalid refresh token")

        if record.used_at is not None or record.revoked_at is not None:
            # Replay: either an attacker or a client bug. We cannot tell which,
            # so assume theft and revoke every token from that login.
            revoke_family(record.family)
            replayed = True
        else:
            replayed = False

        if not replayed:
            if record.expires_at <= timezone.now():
                raise AuthError("Refresh token expired")

            user = record.user
            if not user.is_active:
                raise AuthError("Account is disabled")

            record.used_at = timezone.now()
            record.save(update_fields=["used_at"])
            value, new_record = _new_refresh_token(user, family=record.family)

    if replayed:
        raise AuthError("Refresh token reuse detected; please sign in again")

    return TokenPair(access=issue_access_token(user), refresh_value=value, refresh=new_record)


def revoke_family(family) -> int:
    """Revoke every token from one login session."""
    return RefreshToken.objects.filter(family=family, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )


def logout(token_value: str) -> None:
    """Log out this session. Unknown tokens are ignored: logout always succeeds."""
    record = RefreshToken.objects.filter(token_hash=hash_refresh_token(token_value)).first()
    if record is not None:
        revoke_family(record.family)


def register(email: str, password: str, full_name: str = "", role: str | None = None) -> User:
    email = email.lower().strip()
    if User.objects.filter(email=email).exists():
        raise AuthError("An account with this email already exists")
    return User.objects.create_user(
        email=email, password=password, full_name=full_name, **({"role": role} if role else {})
    )
