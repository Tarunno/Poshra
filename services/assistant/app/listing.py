"""Drafting a listing from a photograph and a few words in Bangla.

The problem this solves is not writing: it is that a weaver in Narayanganj
should not have to write English to sell to Berlin. She photographs the piece,
says what it is in her own language, and gets a listing she can correct.

Three things keep the draft honest rather than merely fluent:

* The craft vocabulary is read from the catalog, so the model picks a craft
  that exists instead of inventing a plausible-sounding one.
* Comparable pieces are sent with it, so the suggested price is anchored to
  what similar work actually sells for here rather than to what the model
  imagines Bangladeshi crafts cost.
* Nothing is published. The draft fills a form; the artisan corrects it and
  decides. The model cannot put anything in the shop, for the same reason it
  cannot take money.
"""

from __future__ import annotations

import logging
from typing import Any

from app.catalog import CatalogClient
from app.llm.base import Photograph

log = logging.getLogger(__name__)

# What a listing form needs. Descriptions are written for the model: they are
# the difference between a title and a good title.
DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": (
                "An English title, at most 70 characters. Name the object and its"
                " most distinctive quality — 'Jute floor mat, indigo stripe', not"
                " 'Beautiful handmade traditional mat'. No marketing adjectives."
            ),
        },
        "description": {
            "type": "string",
            "description": (
                "Two or three sentences for a buyer abroad who has never seen this"
                " craft. Say what it is, how it was made, and what it is for. Use"
                " what the artisan said; do not invent history she did not give."
            ),
        },
        "materials": {
            "type": "string",
            "description": "The materials, as a short phrase. Empty if she did not say.",
        },
        "dimensions": {
            "type": "string",
            "description": "Size if stated or clearly legible in the photograph, else empty.",
        },
        "craft": {
            "type": "string",
            "description": "The slug of the closest craft from the list given. Never a new one.",
        },
        "suggested_price_minor": {
            "type": "integer",
            "description": (
                "A price in poisha (100 poisha = 1 taka), judged against the"
                " comparable pieces given. 0 if there is nothing to judge from."
            ),
        },
        "price_reasoning": {
            "type": "string",
            "description": (
                "One sentence naming which comparable pieces the price was judged"
                " against, so the artisan can disagree with it."
            ),
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "low when the photograph is unclear or the notes are thin.",
        },
    },
    "required": ["title", "description", "craft", "confidence"],
}

SYSTEM = """You write listings for Poshra, a marketplace that sells Bangladeshi
handicrafts to buyers abroad.

You are given a photograph of one piece and the artisan's own words about it,
usually in Bangla. Turn them into a listing in plain English.

Write the way a careful shopkeeper would describe something to a customer who
is genuinely interested: concrete, specific, no marketing language. "Handwoven
in Narayanganj from reclaimed cotton" is worth reading. "Exquisite artisanal
masterpiece" is not.

Never invent facts. If the artisan did not say what something is made of, leave
materials empty rather than guessing from the photograph. If the photograph is
too unclear to tell what the piece is, say so by answering with low confidence
and a short description of what you can see. A listing with a wrong detail
costs the artisan a return and her rating; an incomplete one costs her nothing
but a minute of editing."""


class NothingToDraftFrom(ValueError):
    """Neither a photograph nor any words: there is nothing to work from."""


def _comparable(product: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": product.get("title"),
        "craft": (product.get("craft") or {}).get("slug"),
        "price_minor": product.get("price_minor"),
        "district": product.get("origin_district"),
    }


class ListingDrafter:
    def __init__(self, provider: Any, catalog: CatalogClient) -> None:
        self._provider = provider
        self._catalog = catalog

    async def draft(
        self,
        *,
        notes: str,
        photograph: Photograph | None,
        craft_hint: str = "",
        district: str = "",
    ) -> dict[str, Any]:
        notes = notes.strip()
        if not notes and photograph is None:
            raise NothingToDraftFrom("a photograph or a description is needed")

        crafts = await self._crafts()
        comparables = await self._comparables(craft_hint)

        drafted = await self._provider.structured(
            system=SYSTEM,
            instruction=_instruction(notes, crafts, comparables, district),
            schema=DRAFT_SCHEMA,
            photograph=photograph,
        )
        return self._settle(drafted, crafts)

    async def _crafts(self) -> list[dict[str, Any]]:
        try:
            return await self._catalog.crafts()
        except Exception as error:  # noqa: BLE001 — a draft without the list is still a draft
            log.warning("drafting without the craft list", extra={"error": str(error)})
            return []

    async def _comparables(self, craft_hint: str) -> list[dict[str, Any]]:
        """A handful of pieces to price against, in the same craft when known."""
        params: dict[str, Any] = {"page_size": 6}
        if craft_hint:
            params["craft"] = craft_hint
        try:
            found = await self._catalog.search(params)
        except Exception as error:  # noqa: BLE001
            log.warning("drafting without comparables", extra={"error": str(error)})
            return []
        return [_comparable(product) for product in found]

    def _settle(self, drafted: dict[str, Any], crafts: list[dict[str, Any]]) -> dict[str, Any]:
        """Take the model at its word only where its word can be checked."""
        slugs = {craft["slug"] for craft in crafts if craft.get("slug")}
        craft = str(drafted.get("craft") or "")
        if slugs and craft not in slugs:
            # It was given the list and chose something else. Rather than
            # offering a craft the form cannot accept, leave it for the artisan.
            log.info("model chose a craft that does not exist", extra={"craft": craft})
            craft = ""

        price = drafted.get("suggested_price_minor") or 0
        if not isinstance(price, int) or price < 0:
            price = 0

        return {
            "title": str(drafted.get("title") or "").strip()[:200],
            "description": str(drafted.get("description") or "").strip(),
            "materials": str(drafted.get("materials") or "").strip()[:200],
            "dimensions": str(drafted.get("dimensions") or "").strip()[:100],
            "craft": craft,
            "suggested_price_minor": price,
            "price_reasoning": str(drafted.get("price_reasoning") or "").strip(),
            "confidence": drafted.get("confidence")
            if drafted.get("confidence") in {"high", "medium", "low"}
            else "low",
        }


def _instruction(
    notes: str,
    crafts: list[dict[str, Any]],
    comparables: list[dict[str, Any]],
    district: str,
) -> str:
    lines = []
    if notes:
        lines.append(f"The artisan says, in her own words:\n{notes}")
    else:
        lines.append("The artisan wrote nothing; work from the photograph alone.")

    if district:
        lines.append(f"She works in {district}.")

    if crafts:
        vocabulary = ", ".join(
            f"{craft['slug']} ({craft.get('name', '')})" for craft in crafts if craft.get("slug")
        )
        lines.append(f"Choose the craft from exactly this list: {vocabulary}.")

    if comparables:
        lines.append(
            "Comparable pieces already listed here, for judging the price "
            f"(prices are in poisha): {comparables}"
        )
    else:
        lines.append("There are no comparable pieces to judge a price from; answer 0.")

    return "\n\n".join(lines)
