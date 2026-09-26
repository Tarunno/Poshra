"""Token issuing.

Two different tokens, on purpose:

* **Access token** - a short-lived RS256 JWT. It is *stateless*: Kong verifies
  the signature with the public key and never calls this service. The cost of
  that speed is that it cannot be withdrawn before it expires, so it is
  short-lived and carries only what the gateway and services need.
* **Refresh token** - a long-lived opaque random string, stored hashed in the
  database. It is *stateful*: it can be revoked, rotated and checked for reuse.

Only this service holds the private key, so no other service can mint tokens.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from django.conf import settings

ALGORITHM = "RS256"
REFRESH_TOKEN_BYTES = 32

# A browser's access token lives ten minutes and is refreshed silently. An
# agent has nobody to refresh it: the shopper pasted it in and walked away, so
# a short life means a tool that stops working next Tuesday for no visible
# reason. Thirty days is long enough to be useful and short enough to bound
# the damage of a token left in somebody's config file.
AGENT_TOKEN_TTL_DAYS = 30


@dataclass(frozen=True)
class AccessToken:
    value: str
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(tz=UTC)


def issue_access_token(user) -> AccessToken:
    """Sign a short-lived access token for `user`."""
    issued_at = _now()
    expires_at = issued_at + timedelta(seconds=settings.JWT_ACCESS_TTL_SECONDS)
    payload = {
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        # Unique id: lets a specific token be identified in logs or a deny list.
        "jti": uuid.uuid4().hex,
    }
    value = jwt.encode(
        payload,
        settings.JWT_PRIVATE_KEY,
        algorithm=ALGORITHM,
        # The key id tells a verifier which public key to use, which is what
        # makes key rotation possible without logging everybody out.
        headers={"kid": settings.JWT_KEY_ID},
    )
    return AccessToken(value=value, expires_at=expires_at)


@dataclass(frozen=True)
class AgentTokenIssue:
    """What the caller needs: the token to show once, and the row to store."""

    value: str
    token_id: str
    expires_at: datetime


def issue_agent_token(user, *, token_id: str) -> AgentTokenIssue:
    """Sign a long-lived token for an AI agent acting as `user`.

    Same issuer, same audience and the same key as a browser's token, so the
    gateway verifies it with no special case and services receive the identity
    they already understand. Two claims set it apart: `scope` says this is an
    agent rather than a person at a keyboard, and `jti` is the row in
    AgentToken, which is what makes it revocable.
    """
    issued_at = _now()
    expires_at = issued_at + timedelta(days=AGENT_TOKEN_TTL_DAYS)
    payload = {
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
        "scope": "agent",
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": token_id,
    }
    value = jwt.encode(
        payload,
        settings.JWT_PRIVATE_KEY,
        algorithm=ALGORITHM,
        headers={"kid": settings.JWT_KEY_ID},
    )
    return AgentTokenIssue(value=value, token_id=token_id, expires_at=expires_at)


def decode_access_token(token: str) -> dict:
    """Verify a token locally. Raises jwt.PyJWTError when invalid."""
    return jwt.decode(
        token,
        settings.JWT_PUBLIC_KEY,
        algorithms=[ALGORITHM],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
        options={"require": ["exp", "iat", "sub", "iss", "aud"]},
    )


def generate_refresh_token() -> str:
    """A high-entropy opaque string. Never stored in plaintext."""
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """SHA-256 is right here: the input is already high-entropy random.

    Password hashing needs a slow algorithm (Argon2) because passwords are
    guessable; a 256-bit random token is not.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def public_jwk() -> dict:
    """The public key in JWKS form, for verifiers that fetch keys over HTTP."""
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    key = load_pem_public_key(settings.JWT_PUBLIC_KEY.encode())
    numbers = key.public_numbers()

    def b64(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return {
        "kty": "RSA",
        "use": "sig",
        "alg": ALGORITHM,
        "kid": settings.JWT_KEY_ID,
        "n": b64(numbers.n),
        "e": b64(numbers.e),
    }
