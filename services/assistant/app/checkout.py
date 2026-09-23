"""The cart, as this service sees it.

Everything here acts as the shopper, not as the service: their session cookie
is forwarded and the gateway decides what they may do. The assistant therefore
cannot touch a cart that is not theirs, and holds no privilege of its own to
be stolen — it never sees a password, only a short-lived cookie that lets it do
exactly what the person on the other end could already do.
"""

from __future__ import annotations

from typing import Any

import httpx


class CheckoutClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _headers(self, cookie: str) -> dict[str, str]:
        return {"cookie": cookie} if cookie else {}

    async def cart(self, cookie: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/cart", headers=self._headers(cookie))
            response.raise_for_status()
            return response.json()

    async def add(self, cookie: str, sku_id: str, quantity: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/cart/items",
                headers=self._headers(cookie),
                json={"sku_id": sku_id, "quantity": quantity},
            )
            response.raise_for_status()
            return response.json()


def summarise_cart(cart: dict[str, Any]) -> dict[str, Any]:
    """The cart in the shape the model should talk about."""
    lines = [
        {
            "title": line.get("title") or "a piece that is no longer listed",
            "quantity": line.get("quantity"),
            "line_minor": line.get("line_minor"),
            "available": line.get("available", True),
        }
        for line in cart.get("items") or []
    ]
    return {
        "items": lines,
        "total_minor": cart.get("total_minor", 0),
        "currency": cart.get("currency", "BDT"),
        "empty": not lines,
    }
