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
from app.checkout import CheckoutClient, summarise_cart
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

Putting things in the cart:
- add_to_cart takes the slug of a piece you found. Add something only when the \
shopper asked for it; offering is not agreeing.
- view_cart tells you what is already there. Check before adding, so you do not \
add a second of something they already have.
- You cannot buy anything and must never say that you have. prepare_checkout \
totals the cart and hands over to the checkout page, where the shopper reviews \
it and pays. Say so plainly: tell them what it comes to and that they can \
finish on the checkout page.

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

ADD_TO_CART_TOOL = ToolSpec(
    name="add_to_cart",
    description=(
        "Put a piece in the shopper's cart. Takes the slug of a piece returned "
        "by search_products. Adding is reversible and does not buy anything. "
        "Only add what the shopper actually asked for."
    ),
    parameters={
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": "The slug of a piece, exactly as search returned it.",
            },
            "quantity": {
                "type": "integer",
                "description": "How many, at least 1. Leave out for one.",
            },
        },
        "additionalProperties": False,
        "required": ["slug"],
    },
)

VIEW_CART_TOOL = ToolSpec(
    name="view_cart",
    description=(
        "What is in the shopper's cart now, with the total. Use it before "
        "adding something, so you do not add a second of what they already have."
    ),
    parameters={"type": "object", "properties": {}, "additionalProperties": False},
)

PREPARE_CHECKOUT_TOOL = ToolSpec(
    name="prepare_checkout",
    description=(
        "Total the cart so the shopper can pay for it. This does NOT buy "
        "anything and takes no money: it returns the total, and the interface "
        "then offers a link to the checkout page where they review and pay. "
        "Never tell the shopper an order has been placed."
    ),
    parameters={"type": "object", "properties": {}, "additionalProperties": False},
)

# The tools that act on somebody's behalf, and so need their session.
CART_TOOLS = {"add_to_cart", "view_cart", "prepare_checkout"}

TOOLS = [
    SEARCH_TOOL,
    CRAFTS_TOOL,
    ADD_TO_CART_TOOL,
    VIEW_CART_TOOL,
    PREPARE_CHECKOUT_TOOL,
]
MAX_RESULTS = 8

GAVE_UP = (
    "I am having trouble narrowing that down. Could you tell me a craft or a budget to start from?"
)


class Assistant:
    def __init__(
        self,
        config: Config,
        catalog: CatalogClient,
        checkout: CheckoutClient | None = None,
        provider: Provider | None = None,
    ) -> None:
        self._config = config
        self._catalog = catalog
        self._checkout = checkout or CheckoutClient(config.checkout_url, config.request_timeout)
        # Injectable so the loop can be tested without calling a model: what is
        # worth testing here is how tool results are fed back, not the model.
        self._provider = provider or build_provider(config)

    @property
    def provider(self) -> Provider:
        """Shared with the listing drafter: one provider, one model rotation.

        Two would each learn separately which models are spent, and pay a
        wasted request apiece to find out.
        """
        return self._provider

    async def reply(self, messages: list[dict[str, Any]], cookie: str = "") -> dict[str, Any]:
        """Answer the conversation, and report the pieces the answer rests on.

        The cookie is the shopper's own: cart tools act as them, so the
        assistant can only reach a cart the person on the other end could
        reach themselves.
        """
        conversation = self._provider.start(system=SYSTEM_PROMPT, tools=TOOLS, messages=messages)
        found: dict[str, dict[str, Any]] = {}
        calls = 0
        # Set when the model totals the cart, so the interface knows to offer
        # the way to pay. The model never gets to take the money itself.
        state = {"checkout_ready": False}

        while True:
            turn = await conversation.next_turn()

            if not turn.wants_tools:
                return self._answer(turn.text, found, calls, state)

            results = []
            for call in turn.tool_calls:
                calls += 1
                if calls > self._config.max_tool_calls:
                    # Answer with what is already in hand rather than letting a
                    # confused turn loop against the catalog on our bill.
                    log.warning("tool call budget exhausted", extra={"calls": calls})
                    return self._answer(GAVE_UP, found, calls, state)

                output = await self._run_tool(call.name, call.arguments, found, cookie, state)
                results.append(ToolResult(call=call, content=output))

            conversation.add_tool_results(results)

    def _answer(
        self,
        text: str,
        found: dict[str, dict[str, Any]],
        calls: int,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "reply": text,
            "products": list(found.values())[:MAX_RESULTS],
            "tool_calls": calls,
            # The interface offers the way to pay; the model never takes money.
            "checkout_ready": state["checkout_ready"],
        }

    async def _run_tool(
        self,
        name: str,
        arguments: Any,
        found: dict[str, dict[str, Any]],
        cookie: str,
        state: dict[str, Any],
    ) -> Any:
        arguments = arguments if isinstance(arguments, dict) else {}
        if name in CART_TOOLS and not cookie:
            # Browsing is public; a cart belongs to somebody.
            return {"error": "The shopper is not signed in, so they have no cart."}
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
            if name == "add_to_cart":
                slug = str(arguments.get("slug") or "").strip()
                quantity = arguments.get("quantity")
                quantity = quantity if isinstance(quantity, int) and quantity > 0 else 1

                piece = await self._catalog.by_slug(slug) if slug else None
                if piece is None:
                    # The model invented a slug, or the piece was withdrawn.
                    return {"error": f"There is no piece with the slug {slug!r}."}
                if not piece.get("in_stock"):
                    return {"error": f"{piece['title']} is sold out and cannot be added."}

                cart = await self._checkout.add(cookie, piece["id"], quantity)
                found.setdefault(piece["slug"], piece)
                return {"added": piece["title"], "cart": summarise_cart(cart)}

            if name == "view_cart":
                return {"cart": summarise_cart(await self._checkout.cart(cookie))}

            if name == "prepare_checkout":
                cart = summarise_cart(await self._checkout.cart(cookie))
                if cart["empty"]:
                    return {"cart": cart, "note": "There is nothing to pay for yet."}
                state["checkout_ready"] = True
                return {
                    "cart": cart,
                    "note": (
                        "Nothing has been bought. Tell the shopper the total and "
                        "that they can finish on the checkout page."
                    ),
                }
        except Exception as error:  # noqa: BLE001 — the model should see the failure
            # Handing the error back lets the model say the catalog is
            # unreachable instead of inventing an answer, which is the failure
            # that matters.
            log.error("tool failed", extra={"tool": name, "error": str(error)})
            return {"error": f"That could not be done just now: {error}"}

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
