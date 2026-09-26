from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest
from mcp.server.mcpserver import Context

from app.catalog import CatalogClient
from app.server import build_server
from app.shopper import Caller, CheckoutClient

PIECE = {
    "id": "0192f2c0-0000-7000-8000-000000000001",
    "slug": "indigo-jamdani-saree",
    "title": "Indigo jamdani saree",
    "description": "Woven on a pit loom over eleven weeks.",
    "price_minor": 1450000,
    "currency": "BDT",
    "in_stock": True,
    "lead_time_days": 14,
    "materials": "Handspun cotton, natural indigo",
    "origin_district": "Narayanganj",
    "craft": {"slug": "jamdani", "name": "Jamdani"},
    "artisan": {"display_name": "Rina Begum", "district": "Narayanganj", "division": "dhaka"},
}

CRAFTS = [
    {"slug": "jamdani", "name": "Jamdani", "summary": "Figured muslin woven on a pit loom."},
    {"slug": "nakshi-kantha", "name": "Nakshi kantha", "summary": "Embroidered quilts."},
]


class FakeCatalog(CatalogClient):
    """The marketplace API, stubbed.

    A subclass rather than a mock so the tests break if the client's own shape
    changes — which is the thing most likely to drift out from under us.
    """

    def __init__(self) -> None:
        super().__init__("http://catalog.invalid", 1.0)
        self.searched: list[dict[str, Any]] = []
        # Copied, not shared: a test that marks this piece sold out must not
        # leave it sold out for the next one.
        self.products: list[dict[str, Any]] = [deepcopy(PIECE)]

    async def search(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.searched.append(params)
        return self.products

    async def by_slug(self, slug: str) -> dict[str, Any] | None:
        return next((p for p in self.products if p["slug"] == slug), None)

    async def crafts(self) -> list[dict[str, Any]]:
        return CRAFTS


@pytest.fixture
def catalog() -> FakeCatalog:
    return FakeCatalog()


@pytest.fixture
def server(catalog: FakeCatalog):
    return build_server(catalog)


class FakeCheckout(CheckoutClient):
    """The cart service, stubbed — and it records who it was asked to act as,
    because acting as the wrong shopper is the failure that matters here."""

    def __init__(self) -> None:
        super().__init__("http://checkout.invalid", 1.0)
        self.acted_as: list[Caller] = []
        self.lines: list[dict[str, Any]] = []

    def _snapshot(self) -> dict[str, Any]:
        return {
            "items": list(self.lines),
            "total_minor": sum(line["line_minor"] for line in self.lines),
            "currency": "BDT",
        }

    async def cart(self, caller: Caller) -> dict[str, Any]:
        self.acted_as.append(caller)
        return self._snapshot()

    async def add(self, caller: Caller, sku_id: str, quantity: int) -> dict[str, Any]:
        self.acted_as.append(caller)
        self.lines.append(
            {
                "title": PIECE["title"],
                "quantity": quantity,
                "line_minor": PIECE["price_minor"] * quantity,
                "available": True,
            }
        )
        return self._snapshot()


class Revocations:
    """Stands in for asking the marketplace whether a token is still live."""

    def __init__(self) -> None:
        self.revoked: set[str] = set()
        self.asked: list[str] = []

    async def __call__(self, token_id: str) -> bool:
        self.asked.append(token_id)
        return token_id not in self.revoked


@pytest.fixture
def checkout() -> FakeCheckout:
    return FakeCheckout()


@pytest.fixture
def revocations() -> Revocations:
    return Revocations()


@pytest.fixture
def shop(catalog: FakeCatalog, checkout: FakeCheckout, revocations: Revocations):
    """The whole server: catalogue, cart and revocation checks."""
    return build_server(catalog, checkout, revocations, storefront_url="http://poshra.test")


def ctx(server, headers: dict[str, str] | None = None) -> Context:
    """A tool context carrying the headers the gateway would have injected.

    The SDK is right to warn that request headers are client-supplied input.
    They are an identity assertion here only because of two things outside this
    process: Kong strips any client-sent copy of X-User-Id before setting its
    own, and a NetworkPolicy means Kong is the only thing that can reach this
    service at all. Take either away and this becomes a forgery.
    """
    request = SimpleNamespace(headers=headers if headers is not None else {})
    return Context(
        request_context=SimpleNamespace(request=request, request_id="test"),
        mcp_server=server,
    )
