"""Acting for a shopper rather than for ourselves.

Two things live here, and they are two halves of the same idea.

`Caller` is who the gateway says is on the other end of this request. The
gateway verified the token, injected the identity, and stripped anything the
client tried to claim for itself — so reading a header is reading a fact, not
a hope.

`CheckoutClient` then does the shopper's work by forwarding the shopper's own
credential. This service holds no privilege of its own, which is the point: an
agent can do exactly what the person who minted its token could already do,
and there is no service account here to steal.

The revocation check is the part worth understanding. The gateway can verify a
signature without asking anybody, which is what makes it fast, and is also
precisely why it cannot know the shopper revoked the token an hour ago. So the
tools that act on somebody's behalf ask, and the tools that only read the
public catalogue do not. A revoked token stops being able to touch a cart
within a minute; it never could do anything else.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

# How long a "yes, still live" is trusted. Short enough that a shopper who
# revokes a token sees it stop working while they are still on the page;
# long enough that a busy agent is not re-asking on every tool call.
CHECK_TTL_SECONDS = 60


@dataclass(frozen=True)
class Caller:
    """Who the gateway says this is. Empty when nobody is signed in."""

    user_id: str = ""
    role: str = ""
    # Present only on a token a shopper minted for an agent; a browser session
    # carries none, so its absence means a person at a keyboard.
    token_id: str = ""
    scope: str = ""
    # Forwarded onward so checkout sees the shopper, not us.
    credential: str = ""

    @property
    def signed_in(self) -> bool:
        return bool(self.user_id)

    @property
    def is_agent_token(self) -> bool:
        return bool(self.token_id)


def caller_from(headers: Any) -> Caller:
    """Read the identity the gateway injected."""
    headers = headers or {}

    def get(name: str) -> str:
        value = headers.get(name) or headers.get(name.title()) or ""
        return value.strip() if isinstance(value, str) else ""

    return Caller(
        user_id=get("x-user-id"),
        role=get("x-user-role"),
        token_id=get("x-token-id"),
        scope=get("x-token-scope"),
        credential=get("authorization"),
    )


class TokenStillLive:
    """Asks the marketplace whether an agent token has been revoked.

    Answers are cached per token for a minute. The cache is per pod and that is
    fine: it only ever makes revocation take up to a minute longer on one
    replica, never makes a revoked token work again.
    """

    def __init__(self, base_url: str, timeout: float, ttl: float = CHECK_TTL_SECONDS) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._ttl = ttl
        self._seen: dict[str, tuple[float, bool]] = {}

    async def __call__(self, token_id: str) -> bool:
        now = time.monotonic()
        cached = self._seen.get(token_id)
        if cached and now - cached[0] < self._ttl:
            return cached[1]

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/agent-tokens/introspect",
                    json={"token_id": token_id},
                )
                response.raise_for_status()
                live = bool(response.json().get("active"))
        except httpx.HTTPError:
            # Fail closed. A marketplace that cannot be reached is a
            # marketplace that cannot tell us this token was withdrawn, and
            # spending somebody's revoked token is worse than an agent that
            # says it could not reach the cart.
            return False

        # A "no" is never cached: it is final, and re-asking costs nothing
        # because a revoked token should stop being used.
        if live:
            self._seen[token_id] = (now, True)
        return live


class CheckoutClient:
    """The cart, as this service sees it — always as the shopper."""

    def __init__(self, base_url: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _headers(self, caller: Caller) -> dict[str, str]:
        # The shopper's own bearer token, back through the gateway, which
        # verifies it again and injects the identity checkout trusts. This
        # service never holds a credential of its own.
        return {"Authorization": caller.credential} if caller.credential else {}

    async def cart(self, caller: Caller) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/cart", headers=self._headers(caller))
            response.raise_for_status()
            return response.json()

    async def add(self, caller: Caller, sku_id: str, quantity: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/cart/items",
                headers=self._headers(caller),
                json={"sku_id": sku_id, "quantity": quantity},
            )
            response.raise_for_status()
            return response.json()
