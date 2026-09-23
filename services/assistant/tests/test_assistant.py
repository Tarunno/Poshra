import pytest

from app.assistant import GAVE_UP, MAX_RESULTS, Assistant, _search_params
from app.catalog import summarise
from app.config import Config
from app.llm import ToolCall, Turn

CONFIG = Config(
    provider="gemini",
    api_key="unused",
    model="test-model",
    catalog_url="http://catalog",
    max_tokens=1024,
    max_tool_calls=3,
    request_timeout=1.0,
    llm_timeout=5.0,
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


class FakeConversation:
    """Replays scripted turns and records the results it was handed back."""

    def __init__(self, turns: list[Turn]) -> None:
        self._turns = list(turns)
        self.results_seen: list[list] = []

    async def next_turn(self) -> Turn:
        if not self._turns:
            return Turn(text="(ran out of script)")
        return self._turns.pop(0)

    def add_tool_results(self, results) -> None:
        self.results_seen.append(list(results))


class FakeProvider:
    name = "fake"

    def __init__(self, turns: list[Turn]) -> None:
        self.conversation = FakeConversation(turns)
        self.started_with: dict = {}

    def start(self, *, system, tools, messages):
        self.started_with = {"system": system, "tools": tools, "messages": messages}
        return self.conversation


def call(name: str, arguments: dict | None = None) -> ToolCall:
    return ToolCall(name=name, arguments=arguments or {}, id=f"{name}-0")


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


# --- the loop, whichever model is behind it -----------------------------------


async def test_a_tool_call_is_run_and_its_result_handed_back():
    catalog = FakeCatalog([product("a", "One"), product("b", "Two")])
    provider = FakeProvider(
        [
            Turn(tool_calls=(call("search_products", {"query": "kantha"}),)),
            Turn(text="Here are two pieces."),
        ]
    )

    answer = await Assistant(CONFIG, catalog, provider).reply(
        [{"role": "user", "content": "show me kantha"}]
    )

    assert answer["reply"] == "Here are two pieces."
    assert [p["slug"] for p in answer["products"]] == ["a", "b"]
    assert catalog.searches[0]["q"] == "kantha"
    # Results go back in one batch, matched to the call that asked for them.
    handed_back = provider.conversation.results_seen[0]
    assert len(handed_back) == 1
    assert handed_back[0].call.name == "search_products"


async def test_a_failing_catalog_is_reported_to_the_model_not_hidden():
    provider = FakeProvider(
        [
            Turn(tool_calls=(call("search_products", {"query": "x"}),)),
            Turn(text="I could not reach the catalogue just now."),
        ]
    )

    answer = await Assistant(CONFIG, FakeCatalog(fail=True), provider).reply(
        [{"role": "user", "content": "anything"}]
    )

    # The model must be told the tool failed, so it can say so instead of
    # inventing stock.
    result = provider.conversation.results_seen[0][0].content
    assert "could not be reached" in result["error"]
    assert answer["products"] == []


async def test_the_tool_budget_stops_a_runaway_conversation():
    catalog = FakeCatalog([product("a", "One")])
    # Always asks for another search, never finishes.
    provider = FakeProvider(
        [Turn(tool_calls=(call("search_products", {"query": f"try {i}"}),)) for i in range(10)]
    )

    answer = await Assistant(CONFIG, catalog, provider).reply([{"role": "user", "content": "hmm"}])

    # Every iteration costs money, so the loop is capped rather than trusted.
    assert answer["reply"] == GAVE_UP
    assert answer["tool_calls"] == CONFIG.max_tool_calls + 1
    assert len(catalog.searches) == CONFIG.max_tool_calls


async def test_only_the_pieces_the_tools_returned_come_back():
    many = [product(f"p{i}", f"Piece {i}") for i in range(12)]
    provider = FakeProvider(
        [Turn(tool_calls=(call("search_products"),)), Turn(text="Some pieces.")]
    )

    answer = await Assistant(CONFIG, FakeCatalog(many), provider).reply(
        [{"role": "user", "content": "everything"}]
    )

    assert len(answer["products"]) == MAX_RESULTS


async def test_an_unknown_tool_is_reported_rather_than_crashing():
    provider = FakeProvider([Turn(tool_calls=(call("make_me_a_sandwich"),)), Turn(text="No.")])

    await Assistant(CONFIG, FakeCatalog(), provider).reply([{"role": "user", "content": "hi"}])

    assert "no tool called" in provider.conversation.results_seen[0][0].content["error"]


@pytest.mark.parametrize("tool", ["list_crafts", "search_products"])
async def test_both_tools_are_reachable(tool):
    provider = FakeProvider([Turn(tool_calls=(call(tool),)), Turn(text="Done.")])

    answer = await Assistant(CONFIG, FakeCatalog([product("a", "One")]), provider).reply(
        [{"role": "user", "content": "hi"}]
    )
    assert answer["tool_calls"] == 1
    assert answer["reply"] == "Done."


async def test_the_provider_is_given_the_prompt_and_both_tools():
    provider = FakeProvider([Turn(text="hi")])

    await Assistant(CONFIG, FakeCatalog(), provider).reply([{"role": "user", "content": "hello"}])

    # The prompt and the tools are written once and handed to whichever model
    # is configured — that is the whole point of the seam.
    assert "Poshra" in provider.started_with["system"]
    assert [tool.name for tool in provider.started_with["tools"]] == [
        "search_products",
        "list_crafts",
    ]
