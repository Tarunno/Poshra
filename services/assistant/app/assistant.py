"""Conversational shopping.

The model answers about the catalog by calling tools that hit the same public
API the storefront uses. It has no other source: the system prompt forbids
naming a piece, a price or a maker that a tool did not return, because a
marketplace that invents stock is worse than one that says it has none.

The tools are deliberately few. A wide surface makes a model choose between
near-duplicates; two well-described tools it can combine are easier to get
right than eight it must pick between.

Which model answers is a deployment decision — see app/llm. What lives here is
everything that would otherwise be rewritten per provider: how many tool calls
are affordable, what a failing tool means, and which pieces the answer rests on.
"""

from __future__ import annotations

import logging
from typing import Any

from app.catalog import CatalogClient, summarise
from app.config import Config
from app.llm import Provider, ToolResult, ToolSpec, build_provider

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the shopping assistant for Poshra, a marketplace for handmade crafts \
from Bangladesh — nakshi kantha quilts, jamdani weaving, shitalpati mats, \
terracotta, brass, jute.

How to answer:
- Use the tools to find real pieces. Never name a piece, a price, an artisan or \
a quantity that a tool has not returned to you. If nothing matches, say so and \
suggest what to relax — a higher budget, a different craft, a nearby region.
- Prices are in Bangladeshi taka (BDT). Quote them in taka. If someone gives a \
budget in another currency, convert roughly at 1 USD ≈ 120 BDT, 1 EUR ≈ 130 \
BDT, 1 GBP ≈ 150 BDT, and say the conversion is approximate.
- Refer to a piece by its exact title so the shopper can find it. Do not invent \
URLs; the interface links the pieces you mention.
- Poshra does not have shipping or delivery information yet. If asked where \
something ships, say that plainly rather than guessing.
- Craft vocabulary matters: a shopper may say "quilt" for a nakshi kantha or \
"mat" for shitalpati. Use list_crafts when you are unsure what a word maps to.

How to sound:
- Warm and brief. Two or three sentences, then the pieces.
- Say where a piece comes from and who made it — that is the point of Poshra.
- Never pressure anyone to buy.
"""

SEARCH_TOOL = ToolSpec(
    name="search_products",
    description=(
        "Search the Poshra catalog for pieces that are listed for sale. "
        "Combine filters to narrow a search: a free-text query matches titles, "
        "materials and descriptions, while craft, division and the price bounds "
        "filter exactly. Returns at most 8 pieces with their price, maker and "
        "origin. Call it again with different filters if the first search is "
        "too narrow or too broad."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Free text, e.g. 'indigo saree' or 'wedding gift'. Leave it "
                    "out when the craft filter alone says what is wanted."
                ),
            },
            "craft": {
                "type": "string",
                "description": (
                    "A craft slug from list_crafts, e.g. 'nakshi-kantha'. "
                    "Use this rather than putting the craft name in query."
                ),
            },
            "division": {
                "type": "string",
                "description": (
                    "Administrative division of Bangladesh the maker works in, "
                    "e.g. 'dhaka', 'sylhet', 'rajshahi'."
                ),
            },
            "min_price_minor": {
                "type": "integer",
                "description": "Lowest price in poisha (100 poisha = 1 taka).",
            },
            "max_price_minor": {
                "type": "integer",
                "description": "Highest price in poisha (100 poisha = 1 taka).",
            },
            "in_stock_only": {
                "type": "boolean",
                "description": "Leave out or false to include pieces that are sold out.",
            },
        },
        "additionalProperties": False,
        "required": [],
    },
)

CRAFTS_TOOL = ToolSpec(
    name="list_crafts",
    description=(
        "List every craft Poshra sells, with its slug and a short description. "
        "Use it to map what a shopper said onto a craft slug before searching — "
        "'quilt' is nakshi kantha, 'mat' is shitalpati."
    ),
    parameters={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
        "required": [],
    },
)

TOOLS = [SEARCH_TOOL, CRAFTS_TOOL]
MAX_RESULTS = 8

GAVE_UP = (
    "I am having trouble narrowing that down. Could you tell me a craft or a budget to start from?"
)


class Assistant:
    def __init__(
        self, config: Config, catalog: CatalogClient, provider: Provider | None = None
    ) -> None:
        self._config = config
        self._catalog = catalog
        # Injectable so the loop can be tested without calling a model: what is
        # worth testing here is how tool results are fed back, not the model.
        self._provider = provider or build_provider(config)

    async def reply(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Answer the conversation, and report the pieces the answer rests on."""
        conversation = self._provider.start(system=SYSTEM_PROMPT, tools=TOOLS, messages=messages)
        found: dict[str, dict[str, Any]] = {}
        calls = 0

        while True:
            turn = await conversation.next_turn()

            if not turn.wants_tools:
                return self._answer(turn.text, found, calls)

            results = []
            for call in turn.tool_calls:
                calls += 1
                if calls > self._config.max_tool_calls:
                    # Answer with what is already in hand rather than letting a
                    # confused turn loop against the catalog on our bill.
                    log.warning("tool call budget exhausted", extra={"calls": calls})
                    return self._answer(GAVE_UP, found, calls)

                output = await self._run_tool(call.name, call.arguments, found)
                results.append(ToolResult(call=call, content=output))

            conversation.add_tool_results(results)

    def _answer(self, text: str, found: dict[str, dict[str, Any]], calls: int) -> dict[str, Any]:
        return {
            "reply": text,
            "products": list(found.values())[:MAX_RESULTS],
            "tool_calls": calls,
        }

    async def _run_tool(self, name: str, arguments: Any, found: dict[str, dict[str, Any]]) -> Any:
        arguments = arguments if isinstance(arguments, dict) else {}
        try:
            if name == "list_crafts":
                return {
                    "crafts": [
                        {
                            "slug": craft["slug"],
                            "name": craft["name"],
                            "summary": craft.get("summary", ""),
                        }
                        for craft in await self._catalog.crafts()
                    ]
                }

            if name == "search_products":
                products = await self._catalog.search(_search_params(arguments))
                summaries = [summarise(product) for product in products[:MAX_RESULTS]]
                for product in products[:MAX_RESULTS]:
                    if product.get("slug"):
                        found.setdefault(product["slug"], product)
                return {
                    "pieces": summaries,
                    "note": "" if summaries else "No pieces matched those filters.",
                }
        except Exception as error:  # noqa: BLE001 — the model should see the failure
            # Handing the error back lets the model say the catalog is
            # unreachable instead of inventing an answer, which is the failure
            # that matters.
            log.error("tool failed", extra={"tool": name, "error": str(error)})
            return {"error": f"The catalog could not be reached: {error}"}

        return {"error": f"There is no tool called {name}."}


def _search_params(arguments: dict[str, Any]) -> dict[str, Any]:
    """Map the model's arguments onto the storefront's own query parameters."""
    params: dict[str, Any] = {"page_size": MAX_RESULTS}
    if query := arguments.get("query"):
        params["q"] = str(query)[:200]
    if craft := arguments.get("craft"):
        params["craft"] = str(craft)[:60]
    if division := arguments.get("division"):
        params["division"] = str(division)[:40]
    for key, param in (("min_price_minor", "min_price"), ("max_price_minor", "max_price")):
        value = arguments.get(key)
        if isinstance(value, int) and value >= 0:
            params[param] = value
    if arguments.get("in_stock_only"):
        params["in_stock"] = "true"
    return params
