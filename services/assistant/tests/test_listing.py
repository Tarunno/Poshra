"""Drafting a listing: what the model is told, and what it is not taken at its word on.

No network and no model: the provider is a stub that records what it was asked
and answers from a script.
"""

import pytest

from app.catalog import CatalogClient
from app.listing import DRAFT_SCHEMA, ListingDrafter, NothingToDraftFrom
from app.llm.base import Photograph

CRAFTS = [
    {"slug": "jute-craft", "name": "Jute craft"},
    {"slug": "nakshi-kantha", "name": "Nakshi Kantha"},
]

PRODUCTS = [
    {
        "title": "Jute floor mat, indigo stripe",
        "craft": {"slug": "jute-craft"},
        "price_minor": 430000,
        "origin_district": "Faridpur",
    }
]

GOOD_DRAFT = {
    "title": "Jute floor mat, indigo stripe",
    "description": "Handwoven in Faridpur from locally grown jute.",
    "materials": "Jute",
    "dimensions": "",
    "craft": "jute-craft",
    "suggested_price_minor": 420000,
    "price_reasoning": "Close to the indigo stripe mat already listed.",
    "confidence": "high",
}


class StubProvider:
    def __init__(self, answer: dict) -> None:
        self.answer = answer
        self.asked: dict = {}

    async def structured(self, *, system, instruction, schema, photograph=None):
        self.asked = {
            "system": system,
            "instruction": instruction,
            "schema": schema,
            "photograph": photograph,
        }
        return self.answer


class StubCatalog(CatalogClient):
    def __init__(self, crafts=CRAFTS, products=PRODUCTS) -> None:
        super().__init__("http://catalog", 1.0)
        self._crafts_value = crafts
        self._products = products
        self.searched: dict | None = None

    async def crafts(self):
        if isinstance(self._crafts_value, Exception):
            raise self._crafts_value
        return self._crafts_value

    async def search(self, params):
        self.searched = params
        if isinstance(self._products, Exception):
            raise self._products
        return self._products


def drafter(answer=GOOD_DRAFT, catalog=None):
    provider = StubProvider(answer)
    return ListingDrafter(provider, catalog or StubCatalog()), provider


async def test_the_craft_vocabulary_is_given_to_the_model():
    made, provider = drafter()

    await made.draft(notes="পাটের পাটি", photograph=None)

    # Given the real list, it picks a craft the form can accept instead of
    # inventing one that sounds right.
    assert "jute-craft" in provider.asked["instruction"]
    assert "nakshi-kantha" in provider.asked["instruction"]


async def test_comparable_pieces_anchor_the_price():
    catalog = StubCatalog()
    made, provider = drafter(catalog=catalog)

    await made.draft(notes="পাটের পাটি", photograph=None, craft_hint="jute-craft")

    # Searched in the same craft, and the prices went to the model — otherwise
    # the suggestion is what the model imagines Bangladeshi crafts cost.
    assert catalog.searched == {"page_size": 6, "craft": "jute-craft"}
    assert "430000" in provider.asked["instruction"]


async def test_a_craft_the_model_invented_is_dropped():
    made, _ = drafter({**GOOD_DRAFT, "craft": "macrame"})

    drafted = await made.draft(notes="something", photograph=None)

    # It was given the list and chose otherwise. Offering a craft the form
    # cannot accept is worse than offering none.
    assert drafted["craft"] == ""


async def test_a_negative_price_is_not_a_price():
    made, _ = drafter({**GOOD_DRAFT, "suggested_price_minor": -5})

    drafted = await made.draft(notes="something", photograph=None)

    assert drafted["suggested_price_minor"] == 0


async def test_an_unknown_confidence_is_treated_as_low():
    made, _ = drafter({**GOOD_DRAFT, "confidence": "absolutely certain"})

    drafted = await made.draft(notes="something", photograph=None)

    # Confidence decides how loudly the form warns the artisan to check it.
    assert drafted["confidence"] == "low"


async def test_a_photograph_alone_is_enough():
    made, provider = drafter()

    await made.draft(notes="", photograph=Photograph("image/jpeg", b"\xff\xd8"))

    assert provider.asked["photograph"].media_type == "image/jpeg"
    assert "photograph alone" in provider.asked["instruction"]


async def test_neither_a_photograph_nor_words_is_refused():
    made, _ = drafter()

    with pytest.raises(NothingToDraftFrom):
        await made.draft(notes="   ", photograph=None)


async def test_a_catalogue_that_is_down_does_not_stop_the_draft():
    catalog = StubCatalog(crafts=RuntimeError("catalog down"), products=RuntimeError("down"))
    made, provider = drafter(catalog=catalog)

    drafted = await made.draft(notes="পাটের পাটি", photograph=None)

    # Worse grounding, still a draft: the artisan is mid-form and the
    # catalogue being down is not her problem.
    assert drafted["title"] == GOOD_DRAFT["title"]
    assert "no comparable pieces" in provider.asked["instruction"]


def test_the_schema_asks_for_what_a_listing_form_has():
    # The schema is the contract with the model; a field the form cannot use
    # is a field somebody paid to generate.
    assert set(DRAFT_SCHEMA["required"]) <= set(DRAFT_SCHEMA["properties"])
    assert DRAFT_SCHEMA["properties"]["suggested_price_minor"]["type"] == "integer"
