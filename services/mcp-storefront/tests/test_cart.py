"""The tools that act for a person.

The line this whole feature is built around: an agent may fill a cart and may
never spend money. Everything here either guards that line or guards who is
on the other side of it.
"""

from __future__ import annotations

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from tests.conftest import FakeCatalog, FakeCheckout, Revocations, ctx

SHOPPER = {
    "x-user-id": "0192f2c0-0000-7000-8000-00000000beef",
    "x-user-role": "buyer",
    "x-token-id": "0192f2c0-0000-7000-8000-000000000aaa",
    "x-token-scope": "agent",
    "authorization": "Bearer the-shoppers-own-token",
}
ANONYMOUS: dict[str, str] = {}


async def test_cart_tools_appear_only_when_there_is_a_cart(server, shop) -> None:
    """Three tools without a checkout, six with one — never six that fail."""
    assert len(await server.list_tools()) == 3
    assert {t.name for t in await shop.list_tools()} == {
        "search_products",
        "list_crafts",
        "get_product",
        "view_cart",
        "add_to_cart",
        "prepare_checkout",
    }


async def test_prepare_checkout_never_charges(shop, checkout: FakeCheckout) -> None:
    """The whole safety argument, in one assertion."""
    await shop.call_tool("add_to_cart", {"slug": "indigo-jamdani-saree"}, ctx(shop, SHOPPER))
    result = await shop.call_tool("prepare_checkout", {}, ctx(shop, SHOPPER))

    body = result.structured_content
    assert body["charged"] is False
    assert body["checkout_url"] == "http://poshra.test/checkout"
    # Money changes hands on that page, by a person. Nothing here took any.
    assert body["cart"]["total_minor"] == 1450000


async def test_the_cart_is_touched_as_the_shopper_not_as_us(shop, checkout: FakeCheckout) -> None:
    await shop.call_tool("view_cart", {}, ctx(shop, SHOPPER))
    acted = checkout.acted_as[-1]
    assert acted.user_id == SHOPPER["x-user-id"]
    # Their own credential is forwarded; this service holds none of its own.
    assert acted.credential == "Bearer the-shoppers-own-token"


async def test_anonymous_is_told_how_to_fix_it(shop) -> None:
    with pytest.raises(ToolError, match="agent token"):
        await shop.call_tool("view_cart", {}, ctx(shop, ANONYMOUS))


async def test_a_revoked_token_cannot_touch_the_cart(shop, revocations: Revocations) -> None:
    """What the gateway cannot know: a signature stays valid after revocation."""
    revocations.revoked.add(SHOPPER["x-token-id"])
    with pytest.raises(ToolError, match="revoked"):
        await shop.call_tool("view_cart", {}, ctx(shop, SHOPPER))


async def test_reading_the_catalogue_never_asks_about_tokens(
    shop, revocations: Revocations
) -> None:
    """Public data costs no round trip; only acting for someone does."""
    await shop.call_tool("search_products", {"query": "saree"}, ctx(shop, SHOPPER))
    await shop.call_tool("list_crafts", {}, ctx(shop, SHOPPER))
    assert revocations.asked == []

    await shop.call_tool("view_cart", {}, ctx(shop, SHOPPER))
    assert revocations.asked == [SHOPPER["x-token-id"]]


async def test_a_browser_session_is_not_checked_for_revocation(
    shop, revocations: Revocations
) -> None:
    """No jti means a person at a keyboard, whose session expires on its own."""
    session = {"x-user-id": SHOPPER["x-user-id"], "authorization": "Bearer session"}
    await shop.call_tool("view_cart", {}, ctx(shop, session))
    assert revocations.asked == []


async def test_an_invented_slug_cannot_be_added(shop) -> None:
    with pytest.raises(ToolError, match="no piece with the slug"):
        await shop.call_tool("add_to_cart", {"slug": "golden-unicorn"}, ctx(shop, SHOPPER))


async def test_a_sold_out_piece_cannot_be_added(shop, catalog: FakeCatalog) -> None:
    catalog.products[0]["in_stock"] = False
    with pytest.raises(ToolError, match="sold out"):
        await shop.call_tool("add_to_cart", {"slug": "indigo-jamdani-saree"}, ctx(shop, SHOPPER))


async def test_an_empty_basket_has_nothing_to_check_out(shop) -> None:
    with pytest.raises(ToolError, match="empty"):
        await shop.call_tool("prepare_checkout", {}, ctx(shop, SHOPPER))


async def test_adding_reports_what_went_in(shop) -> None:
    result = await shop.call_tool(
        "add_to_cart", {"slug": "indigo-jamdani-saree", "quantity": 2}, ctx(shop, SHOPPER)
    )
    body = result.structured_content
    assert body["added"] == "Indigo jamdani saree"
    assert body["cart"]["items"][0]["quantity"] == 2
    assert body["cart"]["empty"] is False


async def test_cart_tools_are_not_marked_destructive(shop) -> None:
    """A host asks a human before destructive calls. Filling a basket is
    reversible and charges nothing, so it must not trip that prompt."""
    tools = {t.name: t for t in await shop.list_tools()}
    assert tools["add_to_cart"].annotations.destructive_hint is False
    assert tools["add_to_cart"].annotations.read_only_hint is False
    assert tools["prepare_checkout"].annotations.read_only_hint is True
