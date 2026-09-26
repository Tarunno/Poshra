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

Read-only, all three. Nothing here can change anything, which is what lets the
route in front of them stay open to any signed-in agent.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.catalog import MAX_RESULTS, CatalogClient, search_params

INSTRUCTIONS = """\
Poshra is a marketplace for handmade crafts from Bangladesh — nakshi kantha \
quilts, jamdani weaving, shitalpati mats, terracotta, brass, jute.

Use these tools to find real pieces. Never name a piece, a price, an artisan \
or a quantity that a tool has not returned. Prices are in Bangladeshi taka, \
given here in poisha (100 poisha = 1 taka).

Shoppers use everyday words for crafts — "quilt" for nakshi kantha, "mat" for \
shitalpati. Call list_crafts when you are unsure what a word maps to, and \
search by craft slug rather than by putting the craft's name in the query.\
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


def build_server(catalog: CatalogClient, *, version: str = "0.1.0") -> MCPServer:
    """The server, with its catalog handed in so tests can supply their own."""
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

    @server.custom_route("/healthz", ["GET"], include_in_schema=False)
    async def healthz(_: Request) -> JSONResponse:
        # Beside the protocol rather than in front of it: kubelet asks this a
        # few times a minute and must never open an MCP session to do it.
        return JSONResponse({"status": "ok"})

    return server
