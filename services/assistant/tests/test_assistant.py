import asyncio

import pytest

from app.assistant import GAVE_UP, MAX_RESULTS, RAN_LONG, Assistant, _search_params
from app.catalog import summarise
from app.config import Config
from app.llm import ToolCall, Turn

CONFIG = Config(
    provider="gemini",
    api_key="unused",
    models=("test-model",),
    catalog_url="http://catalog",
    checkout_url="http://checkout",
    max_tokens=1024,
    max_tool_calls=3,
    request_timeout=1.0,
    llm_timeout=5.0,
    turn_budget=25.0,
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


class FakeCheckout:
    """A cart that remembers, so the tools can be exercised without checkout."""

    def __init__(self, items: list[dict] | None = None) -> None:
        self.items = items or []
        self.added: list[tuple[str, int]] = []

    def _cart(self) -> dict:
        total = sum(line["line_minor"] for line in self.items)
        return {"items": self.items, "total_minor": total, "currency": "BDT"}

    async def cart(self, cookie: str) -> dict:
        return self._cart()

    async def add(self, cookie: str, sku_id: str, quantity: int) -> dict:
        self.added.append((sku_id, quantity))
        self.items.append(
            {"title": "One", "quantity": quantity, "line_minor": 560000, "available": True}
        )
        return self._cart()


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

    async def by_slug(self, slug):
        return next((p for p in self.results if p["slug"] == slug), None)


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

    answer = await Assistant(CONFIG, catalog, FakeCheckout(), provider).reply(
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

    answer = await Assistant(CONFIG, FakeCatalog(fail=True), FakeCheckout(), provider).reply(
        [{"role": "user", "content": "anything"}]
    )

    # The model must be told the tool failed, so it can say so instead of
    # inventing stock.
    result = provider.conversation.results_seen[0][0].content
    assert "could not be done" in result["error"]
    assert answer["products"] == []


async def test_the_tool_budget_stops_a_runaway_conversation():
    catalog = FakeCatalog([product("a", "One")])
    # Always asks for another search, never finishes.
    provider = FakeProvider(
        [Turn(tool_calls=(call("search_products", {"query": f"try {i}"}),)) for i in range(10)]
    )

    answer = await Assistant(CONFIG, catalog, FakeCheckout(), provider).reply(
        [{"role": "user", "content": "hmm"}]
    )

    # Every iteration costs money, so the loop is capped rather than trusted.
    assert answer["reply"] == GAVE_UP
    # The count is what was spent, not what was asked for: the call that took
    # it over the line is refused before it is made, so it is not billed and
    # not counted.
    assert answer["tool_calls"] == CONFIG.max_tool_calls
    assert len(catalog.searches) == CONFIG.max_tool_calls


async def test_only_the_pieces_the_tools_returned_come_back():
    many = [product(f"p{i}", f"Piece {i}") for i in range(12)]
    provider = FakeProvider(
        [Turn(tool_calls=(call("search_products"),)), Turn(text="Some pieces.")]
    )

    answer = await Assistant(CONFIG, FakeCatalog(many), FakeCheckout(), provider).reply(
        [{"role": "user", "content": "everything"}]
    )

    assert len(answer["products"]) == MAX_RESULTS


async def test_an_unknown_tool_is_reported_rather_than_crashing():
    provider = FakeProvider([Turn(tool_calls=(call("make_me_a_sandwich"),)), Turn(text="No.")])

    await Assistant(CONFIG, FakeCatalog(), FakeCheckout(), provider).reply(
        [{"role": "user", "content": "hi"}]
    )

    assert "no tool called" in provider.conversation.results_seen[0][0].content["error"]


@pytest.mark.parametrize("tool", ["list_crafts", "search_products"])
async def test_both_tools_are_reachable(tool):
    provider = FakeProvider([Turn(tool_calls=(call(tool),)), Turn(text="Done.")])

    answer = await Assistant(
        CONFIG, FakeCatalog([product("a", "One")]), FakeCheckout(), provider
    ).reply([{"role": "user", "content": "hi"}])
    assert answer["tool_calls"] == 1
    assert answer["reply"] == "Done."


async def test_the_provider_is_given_the_prompt_and_both_tools():
    provider = FakeProvider([Turn(text="hi")])

    await Assistant(CONFIG, FakeCatalog(), FakeCheckout(), provider).reply(
        [{"role": "user", "content": "hello"}]
    )

    # The prompt and the tools are written once and handed to whichever model
    # is configured — that is the whole point of the seam.
    assert "Poshra" in provider.started_with["system"]
    assert [tool.name for tool in provider.started_with["tools"]] == [
        "search_products",
        "list_crafts",
        "add_to_cart",
        "view_cart",
        "prepare_checkout",
    ]


# --- the cart -----------------------------------------------------------------


async def test_adding_resolves_the_slug_the_model_saw_to_a_real_piece():
    catalog = FakeCatalog([product("kantha", "Nakshi kantha throw")])
    checkout = FakeCheckout()
    provider = FakeProvider(
        [
            Turn(tool_calls=(call("add_to_cart", {"slug": "kantha", "quantity": 2}),)),
            Turn(text="Added."),
        ]
    )

    await Assistant(CONFIG, catalog, checkout, provider).reply(
        [{"role": "user", "content": "add the kantha"}], cookie="poshra_at=x"
    )

    # The model works in slugs because that is what search returns; the cart
    # wants an id, and that translation is the service's job.
    assert checkout.added == [("id-kantha", 2)]


async def test_a_slug_the_model_invented_is_refused():
    checkout = FakeCheckout()
    provider = FakeProvider(
        [
            Turn(tool_calls=(call("add_to_cart", {"slug": "a-thing-that-never-existed"}),)),
            Turn(text="I could not find that."),
        ]
    )

    await Assistant(CONFIG, FakeCatalog(), checkout, provider).reply(
        [{"role": "user", "content": "add it"}], cookie="poshra_at=x"
    )

    assert checkout.added == []
    assert "no piece" in provider.conversation.results_seen[0][0].content["error"]


async def test_a_sold_out_piece_is_not_added():
    sold_out = product("gone", "Last one")
    sold_out["in_stock"] = False
    checkout = FakeCheckout()
    provider = FakeProvider(
        [
            Turn(tool_calls=(call("add_to_cart", {"slug": "gone"}),)),
            Turn(text="That one has sold."),
        ]
    )

    await Assistant(CONFIG, FakeCatalog([sold_out]), checkout, provider).reply(
        [{"role": "user", "content": "add it"}], cookie="poshra_at=x"
    )

    assert checkout.added == []
    assert "sold out" in provider.conversation.results_seen[0][0].content["error"]


async def test_a_cart_tool_without_a_session_does_nothing():
    checkout = FakeCheckout()
    provider = FakeProvider([Turn(tool_calls=(call("view_cart"),)), Turn(text="Sign in first.")])

    await Assistant(CONFIG, FakeCatalog(), checkout, provider).reply(
        [{"role": "user", "content": "what is in my cart"}], cookie=""
    )

    # Browsing is public; a cart belongs to somebody. Without their session
    # there is nothing to read and nothing to act on.
    assert "not signed in" in provider.conversation.results_seen[0][0].content["error"]


async def test_preparing_checkout_totals_the_cart_without_buying_anything():
    checkout = FakeCheckout(
        [{"title": "One", "quantity": 1, "line_minor": 560000, "available": True}]
    )
    provider = FakeProvider(
        [Turn(tool_calls=(call("prepare_checkout"),)), Turn(text="That comes to ৳5,600.")]
    )

    answer = await Assistant(CONFIG, FakeCatalog(), checkout, provider).reply(
        [{"role": "user", "content": "I'll take it"}], cookie="poshra_at=x"
    )

    # The model can total a cart and hand over; it has no way to take money,
    # which is a stronger promise than telling it not to.
    assert answer["checkout_ready"] is True
    assert provider.conversation.results_seen[0][0].content["cart"]["total_minor"] == 560000


async def test_an_empty_cart_offers_nothing_to_pay_for():
    provider = FakeProvider(
        [Turn(tool_calls=(call("prepare_checkout"),)), Turn(text="Your cart is empty.")]
    )

    answer = await Assistant(CONFIG, FakeCatalog(), FakeCheckout(), provider).reply(
        [{"role": "user", "content": "checkout"}], cookie="poshra_at=x"
    )

    assert answer["checkout_ready"] is False


# --- how long a shopper waits -------------------------------------------------


class SlowCatalog(FakeCatalog):
    """A catalogue that takes its time, and records when each call ran."""

    def __init__(self, results, delay: float) -> None:
        super().__init__(results)
        self.delay = delay
        self.overlapped = False
        self._running = 0

    async def search(self, params):
        self._running += 1
        # Two in flight at once is the whole point of running them together.
        self.overlapped = self.overlapped or self._running > 1
        try:
            await asyncio.sleep(self.delay)
            return await super().search(params)
        finally:
            self._running -= 1


async def test_tools_asked_for_together_run_together():
    catalog = SlowCatalog([product("a", "One")], delay=0.05)
    provider = FakeProvider(
        [
            Turn(
                tool_calls=(
                    call("search_products", {"query": "kantha"}),
                    call("search_products", {"query": "jamdani"}),
                    call("search_products", {"query": "jute"}),
                )
            ),
            Turn(text="Three sorts of thing."),
        ]
    )

    started = asyncio.get_running_loop().time()
    answer = await Assistant(CONFIG, catalog, FakeCheckout(), provider).reply(
        [{"role": "user", "content": "show me things"}]
    )
    elapsed = asyncio.get_running_loop().time() - started

    assert answer["reply"] == "Three sorts of thing."
    assert len(catalog.searches) == 3
    assert catalog.overlapped, "the searches ran one after another"
    # Three 50ms searches in sequence is 150ms. They are independent requests
    # to the same catalogue, and a shopper should wait for the slowest rather
    # than the sum.
    assert elapsed < 0.12


class Dawdling:
    """A model that never answers in time."""

    name = "slow"

    def __init__(self) -> None:
        self.conversation = self

    def start(self, *, system, tools, messages):
        return self

    async def next_turn(self):
        await asyncio.sleep(10)
        raise AssertionError("the budget should have given up long before this")

    def add_tool_results(self, results):  # pragma: no cover — never reached
        raise AssertionError


async def test_a_turn_that_runs_long_answers_with_what_it_has():
    from app.assistant import RAN_LONG

    budget = Config(**{**CONFIG.__dict__, "turn_budget": 0.05})

    answer = await Assistant(budget, FakeCatalog(), FakeCheckout(), Dawdling()).reply(
        [{"role": "user", "content": "take your time"}]
    )

    # The gateway would cut this off at ninety seconds and the shopper would
    # see a spinner and then an error. Better to stop first and say so.
    assert answer["reply"] == RAN_LONG
    assert answer["products"] == []


# --- the answer as it is written ------------------------------------------------


class StreamingModel(FakeProvider):
    """A model that writes in pieces, and asks for tools in between."""

    def __init__(self, script):
        super().__init__([])
        self.script = list(script)
        self.conversation = self

    def start(self, *, system, tools, messages):
        return self

    async def stream_turn(self):
        from app.llm import TextDelta

        step = self.script.pop(0)
        for text in step.get("deltas", []):
            yield TextDelta(text)
        yield step["turn"]

    def add_tool_results(self, results):
        pass

    async def next_turn(self):  # pragma: no cover — streaming is the path here
        raise AssertionError("the streaming path should not fall back")


async def collect(assistant, question="a wedding gift"):
    return [event async for event in assistant.stream([{"role": "user", "content": question}])]


async def test_the_words_arrive_before_the_answer_does():
    catalog = FakeCatalog([product("a", "Nakshi kantha")])
    model = StreamingModel(
        [
            {"turn": Turn(tool_calls=(call("search_products", {"query": "kantha"}),))},
            {
                "deltas": ["Here are ", "two pieces ", "under ৳8,000."],
                "turn": Turn(text="Here are two pieces under ৳8,000."),
            },
        ]
    )

    events = await collect(Assistant(CONFIG, catalog, FakeCheckout(), model))
    kinds = [event["type"] for event in events]

    # The shopper sees something happening, then words, then the pieces.
    assert kinds == ["status", "delta", "delta", "delta", "answer"]
    assert "".join(e["text"] for e in events if e["type"] == "delta") == (
        "Here are two pieces under ৳8,000."
    )


async def test_the_waiting_is_said_out_loud():
    model = StreamingModel(
        [
            {"turn": Turn(tool_calls=(call("search_products", {"query": "kantha"}),))},
            {"turn": Turn(text="Nothing yet.")},
        ]
    )

    events = await collect(Assistant(CONFIG, FakeCatalog(), FakeCheckout(), model))

    # A silent pause while a search runs is indistinguishable from a page that
    # has stopped working.
    assert events[0] == {"type": "status", "text": "Looking through the workshops…"}


async def test_a_streamed_answer_carries_the_same_pieces_as_a_buffered_one():
    catalog = FakeCatalog([product("a", "Nakshi kantha")])
    model = StreamingModel(
        [
            {"turn": Turn(tool_calls=(call("search_products", {"query": "kantha"}),))},
            {"deltas": ["Two pieces."], "turn": Turn(text="Two pieces.")},
        ]
    )

    events = await collect(Assistant(CONFIG, catalog, FakeCheckout(), model))
    answer = events[-1]

    # A client that reads only the last event gets what /chat returns, which
    # is what makes streaming safe to add rather than to replace.
    assert answer["reply"] == "Two pieces."
    assert [piece["slug"] for piece in answer["products"]] == ["a"]
    assert answer["tool_calls"] == 1
    assert answer["checkout_ready"] is False


async def test_a_stream_that_breaks_still_answers():
    class Broken(StreamingModel):
        async def stream_turn(self):
            raise RuntimeError("the connection went")
            yield  # pragma: no cover

    events = await collect(Assistant(CONFIG, FakeCatalog(), FakeCheckout(), Broken([])))

    # Mid-sentence is the worst moment to say nothing at all.
    assert events[-1]["type"] == "answer"
    assert events[-1]["reply"] == RAN_LONG
