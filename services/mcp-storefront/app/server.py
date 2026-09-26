"""Poshra's storefront, as tools an agent can call.

This is the whole point of the service. Everything an MCP client needs to shop
Poshra it learns at runtime by calling `tools/list`: the names, the argument
schemas and the prose below. Nothing about Poshra has to be written into the
agent.

Two things are worth noticing about how the tools are shaped.

The descriptions are written for a model, not for a developer. They say when
to reach for a tool and what its result means, because the only thing standing
between a shopper and an invented price is how well the model understands what
it is calling. `min_price_minor` names its unit in the argument itself, which
is cheaper than explaining poisha in a sentence the model may skim.

Every tool declares an output schema as well as an input one, by returning a
typed model rather than a loose dict. A client then knows the shape of what
comes back before it calls, and gets it as `structuredContent` beside the text
— so a well-built host can render a price as a price instead of re-parsing
prose it just asked a model to write.

Three of the tools are read-only and need nobody: an agent with no token
browses the public catalogue. The three cart tools act for a person, and the
line they must not cross is the one this whole feature is built around — an
agent may fill a cart and may never spend money. `prepare_checkout` totals the
basket and hands over to a page where a human pays.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.catalog import MAX_RESULTS, CatalogClient, search_params
from app.shopper import Caller, CheckoutClient, TokenStillLive, caller_from

INSTRUCTIONS = """\
Poshra is a marketplace for handmade crafts from Bangladesh — nakshi kantha \
quilts, jamdani weaving, shitalpati mats, terracotta, brass, jute.

Use these tools to find real pieces. Never name a piece, a price, an artisan \
or a quantity that a tool has not returned. Prices are in Bangladeshi taka, \
given here in poisha (100 poisha = 1 taka).

Shoppers use everyday words for crafts — "quilt" for nakshi kantha, "mat" for \
shitalpati. Call list_crafts when you are unsure what a word maps to, and \
search by craft slug rather than by putting the craft's name in the query.

You cannot buy anything and must never say that you have. add_to_cart puts a \
piece in the shopper's basket and is reversible; prepare_checkout totals it \
and returns a link to the page where the shopper reviews and pays. Tell them \
what it comes to and that they can finish there. Add something only when the \
shopper asked for it — offering is not agreeing — and check view_cart first so \
you do not add a second of what they already have.\
"""

# What the protocol lets a server say about a tool beyond its schema. A host
# uses these to decide what needs a human: read-only tools can run unattended,
# destructive ones should not. All three here are reads, so all three say so.
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)


class Piece(BaseModel):
    """One listing, trimmed to what an agent needs to choose between pieces."""

    slug: str = Field(description="Identifies the piece; pass it to get_product.")
    title: str
    craft: str | None = Field(default=None, description="Craft name, e.g. 'Nakshi kantha'.")
    artisan: str | None = Field(default=None, description="Who made it.")
    district: str | None = Field(default=None, description="Where it was made.")
    division: str | None = None
    price_minor: int | None = Field(default=None, description="Price in poisha.")
    currency: str | None = Field(default=None, description="ISO 4217, always BDT today.")
    in_stock: bool | None = None
    lead_time_days: int | None = Field(
        default=None, description="Days before a made-to-order piece ships."
    )
    materials: str | None = None


class PieceDetail(Piece):
    """A single piece, with the prose the listing page shows."""

    description: str | None = None


class SearchResult(BaseModel):
    pieces: list[Piece]
    note: str = Field(
        default="",
        description="Set when nothing matched, saying so in words you can pass on.",
    )


class Craft(BaseModel):
    slug: str = Field(description="Pass this as the craft argument to search_products.")
    name: str
    summary: str = ""


class CraftList(BaseModel):
    crafts: list[Craft]


class CartLine(BaseModel):
    title: str
    quantity: int | None = None
    line_minor: int | None = Field(default=None, description="Price x quantity, in poisha.")
    available: bool = True


class Cart(BaseModel):
    items: list[CartLine]
    total_minor: int = 0
    currency: str = "BDT"
    empty: bool = True


class Added(BaseModel):
    added: str = Field(description="The title of the piece that went in.")
    cart: Cart


class Checkout(BaseModel):
    """What a shopper owes, and where a person — not the model — pays it."""

    cart: Cart
    checkout_url: str = Field(
        description="Send the shopper here to review and pay. Nothing is charged until they do."
    )
    charged: bool = Field(
        default=False,
        description="Always false. This tool cannot take money and never will.",
    )


def _piece(product: dict[str, Any]) -> dict[str, Any]:
    """Flatten a listing.

    The API nests the maker and the craft, because a listing page shows them as
    their own things. A model reading eight of these does better with one flat
    row per piece than with eight little trees to walk.
    """
    artisan = product.get("artisan") or {}
    craft = product.get("craft") or {}
    return {
        "slug": product.get("slug") or "",
        "title": product.get("title") or "",
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


def _cart(cart: dict[str, Any]) -> dict[str, Any]:
    """The cart in the shape the model should talk about.

    `available` is kept because a piece can sell out while it sits in a basket,
    and an agent that says "your two mats come to 6,400 taka" about one that is
    gone has misled somebody.
    """
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


def build_server(
    catalog: CatalogClient,
    checkout: CheckoutClient | None = None,
    still_live: TokenStillLive | None = None,
    *,
    storefront_url: str = "",
    version: str = "0.1.0",
) -> MCPServer:
    """The server, with its backends handed in so tests can supply their own.

    Without a `checkout` the three cart tools are not registered at all. An
    agent then sees six tools minus three rather than three that fail when
    called, which is the difference between a deployment without a cart and a
    cart that is broken.
    """
    server = MCPServer(
        name="poshra-storefront",
        title="Poshra storefront",
        version=version,
        instructions=INSTRUCTIONS,
        website_url="https://github.com/Tarunno/Poshra",
    )

    @server.tool(
        name="search_products",
        title="Search the catalog",
        description=(
            "Search the Poshra catalog for pieces that are listed for sale. "
            "Combine filters to narrow a search: a free-text query matches "
            "titles, materials, makers and place names, while craft, division "
            "and the price bounds filter exactly. Returns at most "
            f"{MAX_RESULTS} pieces. Call it again with different filters if "
            "the first search is too narrow or too broad."
        ),
        annotations=READ_ONLY,
    )
    async def search_products(
        query: Annotated[
            str | None,
            Field(
                description=(
                    "Free text, e.g. 'indigo saree' or 'wedding gift'. Leave it "
                    "out when the craft filter alone says what is wanted."
                )
            ),
        ] = None,
        craft: Annotated[
            str | None,
            Field(
                description=(
                    "A craft slug from list_crafts, e.g. 'nakshi-kantha'. Use "
                    "this rather than putting the craft name in query."
                )
            ),
        ] = None,
        division: Annotated[
            str | None,
            Field(
                description=(
                    "Administrative division of Bangladesh the maker works in, "
                    "e.g. 'dhaka', 'sylhet', 'rajshahi'."
                )
            ),
        ] = None,
        min_price_minor: Annotated[
            int | None,
            Field(description="Lowest price in poisha (100 poisha = 1 taka)."),
        ] = None,
        max_price_minor: Annotated[
            int | None,
            Field(description="Highest price in poisha (100 poisha = 1 taka)."),
        ] = None,
        in_stock_only: Annotated[
            bool,
            Field(description="Leave false to include pieces that are sold out."),
        ] = False,
    ) -> SearchResult:
        products = await catalog.search(
            search_params(query, craft, division, min_price_minor, max_price_minor, in_stock_only)
        )
        pieces = [Piece(**_piece(product)) for product in products[:MAX_RESULTS]]
        return SearchResult(
            pieces=pieces,
            note="" if pieces else "No pieces matched those filters.",
        )

    @server.tool(
        name="list_crafts",
        title="List the crafts",
        description=(
            "List every craft Poshra sells, with its slug and a short "
            "description. Use it to map what a shopper said onto a craft slug "
            "before searching — 'quilt' is nakshi kantha, 'mat' is shitalpati."
        ),
        annotations=READ_ONLY,
    )
    async def list_crafts() -> CraftList:
        return CraftList(
            crafts=[
                Craft(
                    slug=craft.get("slug", ""),
                    name=craft.get("name", ""),
                    summary=craft.get("summary") or "",
                )
                for craft in await catalog.crafts()
            ]
        )

    @server.tool(
        name="get_product",
        title="Read one piece",
        description=(
            "Everything the listing page shows for one piece, including its "
            "full description. Takes a slug exactly as search_products "
            "returned it. Use it when a shopper asks about a particular piece; "
            "search already returns enough to compare several."
        ),
        annotations=READ_ONLY,
    )
    async def get_product(
        slug: Annotated[
            str, Field(description="The slug of a piece, exactly as search returned it.")
        ],
    ) -> PieceDetail:
        product = await catalog.by_slug(slug.strip())
        if product is None:
            # An error rather than an empty result, so the model sees that it
            # asked for something that does not exist and stops citing it.
            raise ToolError(f"There is no piece with the slug {slug!r}.")
        return PieceDetail(**_piece(product), description=product.get("description"))

    # Registered only when there is a checkout to call. An agent then sees
    # three tools instead of six, rather than six where half fail — the
    # difference between a deployment without a cart and a broken cart.
    if checkout is not None:

        async def acting_for(ctx: Context) -> Caller:
            """Who this call is for, or a refusal the model can read and explain.

            Two different noes, deliberately worded apart. "Not signed in" is
            something the shopper can fix by minting a token; "revoked" is
            something they did on purpose and should be told plainly rather than
            left wondering why the cart went quiet.
            """
            caller = caller_from(ctx.headers)
            if not caller.signed_in:
                raise ToolError(
                    "The shopper is not signed in, so they have no cart. They can create a "
                    "Poshra agent token in their account settings and add it to this "
                    "connection as a bearer token."
                )
            revocable = caller.is_agent_token and still_live is not None
            if revocable and not await still_live(caller.token_id):
                raise ToolError(
                    "This token has been revoked or has expired. The shopper can create a "
                    "new one in their Poshra account settings."
                )
            return caller

        @server.tool(
            name="view_cart",
            title="See the basket",
            description=(
                "What is in the shopper's basket now, with the total. Check it "
                "before adding something, so you do not add a second of what they "
                "already have."
            ),
            annotations=ToolAnnotations(
                read_only_hint=True, destructive_hint=False, open_world_hint=False
            ),
        )
        async def view_cart(ctx: Context) -> Cart:
            caller = await acting_for(ctx)
            return Cart(**_cart(await checkout.cart(caller)))

        @server.tool(
            name="add_to_cart",
            title="Put a piece in the basket",
            description=(
                "Put a piece in the shopper's basket. Takes the slug of a piece "
                "returned by search_products. Adding is reversible and does not "
                "buy anything. Only add what the shopper actually asked for — "
                "offering something is not the same as them agreeing to it."
            ),
            annotations=ToolAnnotations(
                read_only_hint=False,
                # Reversible: the shopper can take it back out, and nothing is
                # charged. A host that asks a human before destructive calls need
                # not ask before this one.
                destructive_hint=False,
                idempotent_hint=False,
                open_world_hint=False,
            ),
        )
        async def add_to_cart(
            ctx: Context,
            slug: Annotated[
                str, Field(description="The slug of a piece, exactly as search returned it.")
            ],
            quantity: Annotated[int, Field(description="How many, at least 1.", ge=1)] = 1,
        ) -> Added:
            caller = await acting_for(ctx)

            # Resolved here rather than trusted: the model works in slugs, the
            # cart needs an id, and a slug that does not exist is a slug the model
            # invented. Checking stock first turns "sold out" into something it
            # can say instead of a failure it has to interpret.
            piece = await catalog.by_slug(slug.strip())
            if piece is None:
                raise ToolError(f"There is no piece with the slug {slug!r}.")
            if not piece.get("in_stock"):
                raise ToolError(f"{piece['title']} is sold out and cannot be added.")

            cart = await checkout.add(caller, piece["id"], quantity)
            return Added(added=piece["title"], cart=Cart(**_cart(cart)))

        @server.tool(
            name="prepare_checkout",
            title="Total the basket",
            description=(
                "Total the basket so the shopper can pay for it. This does NOT buy "
                "anything and takes no money: it returns the total and a link to "
                "the checkout page, where the shopper reviews the order and pays. "
                "Never tell the shopper an order has been placed."
            ),
            annotations=ToolAnnotations(
                # Reads and totals; the paying happens on a page, by a person.
                read_only_hint=True,
                destructive_hint=False,
                open_world_hint=False,
            ),
        )
        async def prepare_checkout(ctx: Context) -> Checkout:
            caller = await acting_for(ctx)
            cart = Cart(**_cart(await checkout.cart(caller)))
            if cart.empty:
                raise ToolError("The basket is empty, so there is nothing to check out.")
            return Checkout(cart=cart, checkout_url=f"{storefront_url}/checkout")

    # ---- Resources -------------------------------------------------------
    #
    # A resource is not a tool, and the difference is who decides. A tool is
    # reached for by the *model*, mid-turn, because it worked out that it
    # needed one. A resource is attached by the *application* — the host puts
    # it in front of the model the way you would attach a file to a message —
    # and is addressed by URI rather than chosen by name.
    #
    # Poshra publishes the same catalogue both ways on purpose. An assistant
    # answering "what do you have under 5000 taka" searches. A person who is
    # already looking at a piece and opens a chat about it wants that piece in
    # context without the model having to guess the slug and go and find it.

    @server.resource(
        "poshra://crafts",
        name="crafts",
        title="Every craft Poshra sells",
        description=(
            "The list of crafts with their slugs, as context rather than as a "
            "tool call. Attach it when a conversation is about Bangladeshi "
            "crafts generally rather than about one piece."
        ),
        mime_type="application/json",
    )
    async def crafts_resource() -> str:
        crafts = await catalog.crafts()
        return json.dumps(
            [
                {
                    "slug": craft.get("slug", ""),
                    "name": craft.get("name", ""),
                    "summary": craft.get("summary") or "",
                }
                for craft in crafts
            ],
            ensure_ascii=False,
            indent=2,
        )

    @server.resource(
        "poshra://product/{slug}",
        name="product",
        title="One piece",
        description=(
            "Everything the listing page shows for one piece, addressed by "
            "slug. Attach it when the shopper is already looking at something."
        ),
        mime_type="application/json",
    )
    async def product_resource(slug: str) -> str:
        product = await catalog.by_slug(slug.strip())
        if product is None:
            raise ResourceError(f"There is no piece with the slug {slug!r}.")
        return json.dumps(
            {**_piece(product), "description": product.get("description")},
            ensure_ascii=False,
            indent=2,
        )

    # ---- Prompts ---------------------------------------------------------
    #
    # The third thing a client decides: a prompt is chosen by the *user*, and
    # surfaces in a host as a slash command or a menu item. These are the
    # openings people actually arrive with, written once here so that every
    # agent asks them the same way rather than each one improvising.

    @server.prompt(
        name="find_a_gift",
        title="Find a gift",
        description="Shop for somebody else, given an occasion and a budget.",
    )
    def find_a_gift(
        occasion: Annotated[
            str, Field(description="What it is for, e.g. 'a wedding', 'a new home'.")
        ],
        budget_taka: Annotated[str, Field(description="What they want to spend, in taka.")] = "",
    ) -> str:
        budget = f" We can spend about {budget_taka} taka." if budget_taka else ""
        return (
            f"I am looking for a handmade gift from Bangladesh for {occasion}.{budget} "
            "Search Poshra, show me a few pieces that fit, and say who made each one "
            "and where it comes from. Do not put anything in my basket yet."
        )

    @server.prompt(
        name="about_this_craft",
        title="About this craft",
        description="Learn what a craft is, and see pieces of it that are for sale.",
    )
    def about_this_craft(
        craft: Annotated[str, Field(description="A craft slug or its everyday name.")],
    ) -> str:
        return (
            f"Tell me about {craft} as a Bangladeshi craft — what it is, how it is "
            "made, and where it comes from. Use list_crafts to get it right rather "
            "than from memory, then show me a few pieces of it that Poshra has now."
        )

    @server.custom_route("/healthz", ["GET"], include_in_schema=False)
    async def healthz(_: Request) -> JSONResponse:
        # Beside the protocol rather than in front of it: kubelet asks this a
        # few times a minute and must never open an MCP session to do it.
        return JSONResponse({"status": "ok"})

    return server
