"""Resources and prompts — the two thirds of MCP most servers skip.

The distinction they exist to draw: a tool is reached for by the *model*, a
resource is attached by the *application*, and a prompt is chosen by the
*user*. Same catalogue behind all three; three different people deciding.
"""

from __future__ import annotations

import json

import pytest
from mcp.server.mcpserver.exceptions import ResourceError

from tests.conftest import ctx


async def test_the_craft_list_is_offered_as_context_too(server) -> None:
    resources = {str(r.uri): r for r in await server.list_resources()}
    assert "poshra://crafts" in resources
    assert resources["poshra://crafts"].mime_type == "application/json"


async def test_a_piece_is_addressable_by_slug(server) -> None:
    """A host attaches the piece the shopper is looking at, rather than making
    the model guess the slug and go and search for it."""
    templates = {t.uri_template for t in await server.list_resource_templates()}
    assert "poshra://product/{slug}" in templates

    read = await server.read_resource("poshra://product/indigo-jamdani-saree")
    piece = json.loads(next(iter(read)).content)
    assert piece["title"] == "Indigo jamdani saree"
    assert piece["description"].startswith("Woven on a pit loom")


async def test_an_unknown_piece_is_an_error_not_an_empty_document(server) -> None:
    with pytest.raises(ResourceError, match="no piece with the slug"):
        await server.read_resource("poshra://product/invented-by-the-host")


async def test_crafts_resource_carries_the_slug_search_wants(server) -> None:
    read = await server.read_resource("poshra://crafts")
    crafts = json.loads(next(iter(read)).content)
    assert [c["slug"] for c in crafts] == ["jamdani", "nakshi-kantha"]


async def test_prompts_are_the_openings_people_actually_arrive_with(server) -> None:
    prompts = {p.name: p for p in await server.list_prompts()}
    assert set(prompts) == {"find_a_gift", "about_this_craft"}
    assert [a.name for a in prompts["find_a_gift"].arguments] == ["occasion", "budget_taka"]


async def test_a_gift_prompt_carries_the_budget_when_given(server) -> None:
    with_budget = await server.get_prompt(
        "find_a_gift", {"occasion": "a wedding", "budget_taka": "5000"}
    )
    text = with_budget.messages[0].content.text
    assert "a wedding" in text
    assert "5000 taka" in text
    # The opening says not to buy anything, because the shopper has not asked.
    assert "Do not put anything in my basket" in text


async def test_a_gift_prompt_reads_naturally_without_one(server) -> None:
    """An optional argument left out must not leave a sentence fragment."""
    without = await server.get_prompt("find_a_gift", {"occasion": "a new home"})
    text = without.messages[0].content.text
    assert "taka" not in text
    assert "  " not in text


async def test_the_craft_prompt_tells_the_model_to_look_rather_than_recall(server) -> None:
    prompt = await server.get_prompt("about_this_craft", {"craft": "shitalpati"})
    assert "list_crafts" in prompt.messages[0].content.text


async def test_resources_need_no_shopper(server) -> None:
    """They read the public catalogue, so a host with no token can attach them."""
    read = await server.read_resource("poshra://crafts", ctx(server, {}))
    assert json.loads(next(iter(read)).content)
