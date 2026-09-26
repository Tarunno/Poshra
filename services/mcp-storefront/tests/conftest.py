from __future__ import annotations

from typing import Any

import pytest

from app.catalog import CatalogClient
from app.server import build_server

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
        self.products: list[dict[str, Any]] = [PIECE]

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
