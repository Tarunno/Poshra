"""The catalog, as this service sees it.

Read-only and unauthenticated: the storefront is public, so the assistant
browses exactly what a visitor can. It never reaches the database — that
belongs to marketplace — and it never sees a draft.
"""

from __future__ import annotations

from typing import Any

import httpx


class CatalogClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def search(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/products", params=params)
            response.raise_for_status()
            return response.json().get("results", [])

    async def crafts(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/crafts")
            response.raise_for_status()
            return response.json()


def summarise(product: dict[str, Any]) -> dict[str, Any]:
    """Trim a listing to what the model needs to answer about it.

    Descriptions run to paragraphs, and a dozen of them crowd out the
    conversation for no benefit: the model is choosing between pieces here, not
    reciting them. The page it links to has the full text.
    """
    artisan = product.get("artisan") or {}
    craft = product.get("craft") or {}
    return {
        "slug": product.get("slug"),
        "title": product.get("title"),
        "craft": craft.get("name"),
        "artisan": artisan.get("display_name"),
        "district": product.get("origin_district") or artisan.get("district"),
        "division": artisan.get("division"),
        "price_minor": product.get("price_minor"),
        "currency": product.get("currency"),
        "in_stock": product.get("in_stock"),
        "lead_time_days": product.get("lead_time_days"),
        "materials": product.get("materials"),
    }
