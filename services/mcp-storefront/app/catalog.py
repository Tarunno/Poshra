"""The catalog, as this service sees it.

Read-only and unauthenticated: the storefront is public, so an agent browses
exactly what a visitor can. This service owns no database — it calls the same
marketplace API the web storefront calls, which is the rule the whole repo
runs on.
"""

from __future__ import annotations

from typing import Any

import httpx

MAX_RESULTS = 8


class CatalogClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def search(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/products", params=params)
            response.raise_for_status()
            return response.json().get("results", [])

    async def by_slug(self, slug: str) -> dict[str, Any] | None:
        """One listing, or None if there is no such piece."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/products/{slug}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def crafts(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/crafts")
            response.raise_for_status()
            return response.json()


def search_params(
    query: str | None,
    craft: str | None,
    division: str | None,
    min_price_minor: int | None,
    max_price_minor: int | None,
    in_stock_only: bool,
) -> dict[str, Any]:
    """Map the tool's arguments onto the storefront's own query parameters.

    The names differ on purpose. A tool argument is written for a model —
    `min_price_minor` says what the unit is, which stops it sending taka where
    poisha are wanted. A query parameter is written for the storefront's URL
    bar. Translating here keeps either side free to be renamed.
    """
    params: dict[str, Any] = {"page_size": MAX_RESULTS}
    if query:
        params["q"] = query[:200]
    if craft:
        params["craft"] = craft[:60]
    if division:
        params["division"] = division[:40]
    if min_price_minor is not None and min_price_minor >= 0:
        params["min_price"] = min_price_minor
    if max_price_minor is not None and max_price_minor >= 0:
        params["max_price"] = max_price_minor
    if in_stock_only:
        params["in_stock"] = "true"
    return params
