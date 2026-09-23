from types import SimpleNamespace

import pytest

from app.assistant import MAX_RESULTS, Assistant, _search_params
from app.catalog import summarise
from app.config import Config

CONFIG = Config(
    anthropic_api_key="unused",
    catalog_url="http://catalog",
    model="claude-opus-5",
    max_tokens=1024,
    max_tool_calls=3,
    request_timeout=1.0,
)


def product(slug: str, title: str, price: int = 560000) -> dict:
    return {
        "id": f"id-{slug}",
        "slug": slug,
        "title": title,
        "description": "A very long description " * 50,
        "price_minor": price,
        "currency": "BDT",
        "in_stock": True,
        "lead_time_days": 7,
        "materials": "Cotton",
        "origin_district": "Jamalpur",
        "artisan": {"display_name": "Rina Akter", "division": "dhaka", "district": "Narayanganj"},
        "craft": {"name": "Nakshi kantha", "slug": "nakshi-kantha"},
    }


class FakeCatalog:
    def __init__(self, results: list[dict] | None = None, fail: bool = False) -> None:
        self.results = results if results is not None else []
        self.fail = fail
        self.searches: list[dict] = []

    async def search(self, params):
        self.searches.append(params)
        if self.fail:
            raise RuntimeError("connection refused")
        return self.results

    async def crafts(self):
        return [{"slug": "nakshi-kantha", "name": "Nakshi kantha", "summary": "Quilts"}]


def text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def tool_block(name: str, arguments: dict, block_id: str = "t1"):
    return SimpleNamespace(type="tool_use", name=name, input=arguments, id=block_id)


class FakeClient:
    """Replays a scripted sequence of model responses and records what it was sent."""

    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = list(responses)
        self.requests: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs):
        self.requests.append(kwargs)
        return self._responses.pop(0)


# --- the argument mapping -----------------------------------------------------


def test_a_budget_becomes_the_catalogs_own_price_filter():
    params = _search_params({"query": "kantha", "max_price_minor": 1200000})
    # The model speaks in poisha because the tool says so; the storefront's
    # parameter is named differently, and that translation lives here.
    assert params["q"] == "kantha"
    assert params["max_price"] == 1200000


def test_nonsense_arguments_are_dropped_rather_than_forwarded():
    params = _search_params({"max_price_minor": "lots", "in_stock_only": False, "craft": None})
    assert "max_price" not in params
    assert "in_stock" not in params
    assert "craft" not in params


def test_a_summary_leaves_out_the_prose():
    trimmed = summarise(product("kantha", "Nakshi kantha, lotus"))
    assert trimmed["artisan"] == "Rina Akter"
    assert trimmed["price_minor"] == 560000
    # Descriptions run to paragraphs and would crowd out the conversation.
    assert "description" not in trimmed


# --- the loop -----------------------------------------------------------------


async def test_tool_results_go_back_in_one_user_message():
    catalog = FakeCatalog([product("a", "One"), product("b", "Two")])
    client = FakeClient(
        [
            SimpleNamespace(
                stop_reason="tool_use",
                content=[tool_block("search_products", {"query": "kantha"})],
            ),
            SimpleNamespace(stop_reason="end_turn", content=[text_block("Here are two pieces.")]),
        ]
    )
    assistant = Assistant(CONFIG, catalog, client)

    answer = await assistant.reply([{"role": "user", "content": "show me kantha"}])

    assert answer["reply"] == "Here are two pieces."
    assert [p["slug"] for p in answer["products"]] == ["a", "b"]
    # Splitting results across messages teaches the model to stop asking for
    # several things at once, so they must arrive together.
    last_sent = client.requests[-1]["messages"][-1]
    assert last_sent["role"] == "user"
    assert all(block["type"] == "tool_result" for block in last_sent["content"])


async def test_a_failing_catalog_is_reported_to_the_model_not_hidden():
    catalog = FakeCatalog(fail=True)
    client = FakeClient(
        [
            SimpleNamespace(
                stop_reason="tool_use", content=[tool_block("search_products", {"query": "x"})]
            ),
            SimpleNamespace(
                stop_reason="end_turn",
                content=[text_block("I could not reach the catalogue just now.")],
            ),
        ]
    )
    assistant = Assistant(CONFIG, catalog, client)

    answer = await assistant.reply([{"role": "user", "content": "anything"}])

    # The model must be told the tool failed, so it can say so instead of
    # inventing stock.
    result = client.requests[-1]["messages"][-1]["content"][0]["content"]
    assert "could not be reached" in result
    assert answer["products"] == []


async def test_the_tool_budget_stops_a_runaway_conversation():
    catalog = FakeCatalog([product("a", "One")])
    # Always asks for another search, never finishes.
    responses = [
        SimpleNamespace(
            stop_reason="tool_use",
            content=[tool_block("search_products", {"query": f"try {i}"}, f"t{i}")],
        )
        for i in range(10)
    ]
    assistant = Assistant(CONFIG, catalog, FakeClient(responses))

    answer = await assistant.reply([{"role": "user", "content": "hmm"}])

    # Every iteration costs money, so the loop is capped rather than trusted.
    assert answer["tool_calls"] == CONFIG.max_tool_calls + 1
    assert len(catalog.searches) == CONFIG.max_tool_calls
    assert "narrow" in answer["reply"]


async def test_only_the_pieces_the_tools_returned_come_back():
    many = [product(f"p{i}", f"Piece {i}") for i in range(12)]
    catalog = FakeCatalog(many)
    client = FakeClient(
        [
            SimpleNamespace(stop_reason="tool_use", content=[tool_block("search_products", {})]),
            SimpleNamespace(stop_reason="end_turn", content=[text_block("Some pieces.")]),
        ]
    )

    answer = await Assistant(CONFIG, catalog, client).reply(
        [{"role": "user", "content": "everything"}]
    )

    assert len(answer["products"]) == MAX_RESULTS


@pytest.mark.parametrize("tool", ["list_crafts", "search_products"])
async def test_both_tools_are_reachable(tool):
    catalog = FakeCatalog([product("a", "One")])
    client = FakeClient(
        [
            SimpleNamespace(stop_reason="tool_use", content=[tool_block(tool, {})]),
            SimpleNamespace(stop_reason="end_turn", content=[text_block("Done.")]),
        ]
    )

    answer = await Assistant(CONFIG, catalog, client).reply([{"role": "user", "content": "hi"}])
    assert answer["tool_calls"] == 1
    assert answer["reply"] == "Done."
