"""What an agent sees, and what it gets back."""

from __future__ import annotations

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from tests.conftest import FakeCatalog


async def test_lists_three_read_only_tools(server) -> None:
    tools = {tool.name: tool for tool in await server.list_tools()}
    assert set(tools) == {"search_products", "list_crafts", "get_product"}
    for tool in tools.values():
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True


async def test_every_tool_publishes_both_schemas(server) -> None:
    """A client should know the shape of the answer before it calls."""
    for tool in await server.list_tools():
        assert tool.input_schema["type"] == "object"
        assert tool.output_schema is not None, tool.name


async def test_search_arguments_reach_the_storefront(server, catalog: FakeCatalog) -> None:
    await server.call_tool(
        "search_products",
        {"query": "saree", "craft": "jamdani", "max_price_minor": 2000000, "in_stock_only": True},
    )
    assert catalog.searched == [
        {
            "page_size": 8,
            "q": "saree",
            "craft": "jamdani",
            "max_price": 2000000,
            "in_stock": "true",
        }
    ]


async def test_search_returns_flat_structured_pieces(server) -> None:
    result = await server.call_tool("search_products", {"query": "saree"})
    assert result.is_error is False
    piece = result.structured_content["pieces"][0]
    # Flattened: the maker and the craft arrive as names, not as nested objects.
    assert piece["artisan"] == "Rina Begum"
    assert piece["craft"] == "Jamdani"
    assert piece["price_minor"] == 1450000


async def test_empty_search_says_so_in_words(server, catalog: FakeCatalog) -> None:
    catalog.products = []
    result = await server.call_tool("search_products", {"query": "nothing"})
    assert result.structured_content["pieces"] == []
    assert result.structured_content["note"]


async def test_get_product_includes_the_description(server) -> None:
    result = await server.call_tool("get_product", {"slug": "indigo-jamdani-saree"})
    assert result.structured_content["description"].startswith("Woven on a pit loom")


async def test_unknown_slug_is_an_error_not_an_empty_piece(server) -> None:
    """The model must see that it asked for something that does not exist."""
    with pytest.raises(ToolError, match="no piece with the slug"):
        await server.call_tool("get_product", {"slug": "invented-by-the-model"})


async def test_list_crafts_carries_the_slug_search_wants(server) -> None:
    result = await server.call_tool("list_crafts", {})
    slugs = [craft["slug"] for craft in result.structured_content["crafts"]]
    assert slugs == ["jamdani", "nakshi-kantha"]
