"""What Gemini needs that Claude does not, and the other way round.

No network: every one of these is a conversion, and conversions are where the
differences between providers actually live.
"""

from app.assistant import CRAFTS_TOOL, SEARCH_TOOL
from app.llm.base import ToolCall, ToolResult
from app.llm.gemini import (
    GeminiConversation,
    GeminiEndpoint,
    ModelRotation,
    _clean_schema,
    _declaration,
)


def conversation(**overrides):
    defaults = dict(
        endpoint=GeminiEndpoint("unused", ModelRotation(["gemini-3.6-flash"]), 5.0),
        max_tokens=512,
        system="be helpful",
        tools=[SEARCH_TOOL, CRAFTS_TOOL],
        messages=[{"role": "user", "content": "hello"}],
    )
    return GeminiConversation(**{**defaults, **overrides})


def test_schema_keywords_gemini_refuses_are_stripped():
    cleaned = _clean_schema(SEARCH_TOOL.parameters)
    # Sent as written, additionalProperties makes Gemini reject the whole
    # request rather than ignore the key.
    assert "additionalProperties" not in cleaned
    assert cleaned["properties"]["max_price_minor"]["type"] == "integer"
    # The descriptions are the part that makes the model choose well, so they
    # must survive the trimming.
    assert "poisha" in cleaned["properties"]["max_price_minor"]["description"]


def test_a_tool_that_takes_nothing_omits_parameters_entirely():
    # An empty properties object is refused; the key has to be absent.
    assert "parameters" not in _declaration(CRAFTS_TOOL)
    assert "parameters" in _declaration(SEARCH_TOOL)


def test_the_assistants_turns_are_relabelled_as_model():
    talk = conversation(
        messages=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "a kantha please"},
        ]
    )
    assert [c["role"] for c in talk._contents] == ["user", "model", "user"]


def test_a_function_call_becomes_a_tool_call():
    talk = conversation()
    turn = talk._read(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "search_products",
                                    "args": {"query": "kantha", "max_price_minor": 1200000},
                                }
                            }
                        ]
                    }
                }
            ]
        }
    )

    assert turn.wants_tools
    assert turn.tool_calls[0].name == "search_products"
    assert turn.tool_calls[0].arguments["max_price_minor"] == 1200000
    # Gemini gives no id, so one is invented — the loop matches results to
    # calls and needs something to match on.
    assert turn.tool_calls[0].id


def test_the_turn_is_remembered_so_the_next_request_knows_it_asked():
    talk = conversation()
    before = len(talk._contents)
    talk._read(
        {"candidates": [{"content": {"parts": [{"functionCall": {"name": "list_crafts"}}]}}]}
    )
    assert len(talk._contents) == before + 1
    assert talk._contents[-1]["role"] == "model"


def test_plain_text_is_the_final_answer():
    talk = conversation()
    turn = talk._read({"candidates": [{"content": {"parts": [{"text": "Two pieces."}]}}]})
    assert turn.text == "Two pieces."
    assert not turn.wants_tools


def test_a_blocked_prompt_returns_nothing_rather_than_raising():
    # A prompt can be refused outright, leaving no candidate at all.
    assert conversation()._read({"promptFeedback": {"blockReason": "SAFETY"}}).text == ""


def test_a_tool_result_that_is_not_an_object_is_wrapped():
    talk = conversation()
    call = ToolCall(name="list_crafts", arguments={}, id="list_crafts-0")
    talk.add_tool_results([ToolResult(call=call, content=["a", "b"])])

    response = talk._contents[-1]["parts"][0]["functionResponse"]
    # Gemini requires an object here; a bare list is a 400.
    assert response["name"] == "list_crafts"
    assert response["response"] == {"result": ["a", "b"]}


# --- being told "not now" ------------------------------------------------------


class FakeResponse:
    def __init__(self, status: int, body: dict | None = None, headers: dict | None = None):
        self.status_code = status
        self._body = body or {}
        self.headers = headers or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected raise for {self.status_code}")


def test_a_retry_delay_is_taken_from_the_header():
    from app.llm.gemini import _retry_after

    assert _retry_after(FakeResponse(429, headers={"retry-after": "12"})) == 12.0


def test_a_retry_delay_is_taken_from_googles_error_body():
    from app.llm.gemini import _retry_after

    # Google usually says how long to wait inside the error rather than in a
    # header, and waiting the right amount beats guessing.
    response = FakeResponse(429, {"error": {"details": [{"retryDelay": "37s"}]}})
    assert _retry_after(response) == 37.0


def test_no_retry_delay_is_not_an_error():
    from app.llm.gemini import _retry_after

    assert _retry_after(FakeResponse(503, {"error": {"message": "busy"}})) is None


def test_a_long_retry_delay_fails_fast_instead_of_hanging():
    from app.llm.gemini import MAX_WAIT, _retry_after

    # When Google names a delay this long the quota is spent, not busy.
    # Waiting it out inside a request turns "try again shortly" into a page
    # that looks frozen, and the gateway times out first anyway.
    long_delay = _retry_after(FakeResponse(429, {"error": {"details": [{"retryDelay": "47s"}]}}))
    assert long_delay is not None and long_delay > MAX_WAIT
