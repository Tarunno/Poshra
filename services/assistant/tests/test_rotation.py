"""Falling down the list of models instead of failing the shopper.

No network: httpx is driven by a transport that answers from a script, so the
quota these test is nobody's.
"""

import asyncio

import httpx
import pytest

from app.assistant import CRAFTS_TOOL, SEARCH_TOOL
from app.llm.gemini import (
    GeminiConversation,
    GeminiEndpoint,
    ModelRotation,
    RateLimited,
)

MODELS = ["first", "second", "third"]


def answer(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def scripted(script: dict[str, httpx.Response]):
    """A transport that answers per model, and records who was asked."""
    asked: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        model = request.url.path.split("/models/")[1].split(":")[0]
        asked.append(model)
        return script[model]

    return httpx.MockTransport(handle), asked


def conversation(rotation, transport, monkeypatch):
    # One transport for every client the conversation opens.
    real = httpx.AsyncClient

    def client(*args, **kwargs):
        return real(*args, **{**kwargs, "transport": transport})

    monkeypatch.setattr(httpx, "AsyncClient", client)
    return GeminiConversation(
        endpoint=GeminiEndpoint("unused", rotation, 5.0),
        max_tokens=512,
        system="be helpful",
        tools=[SEARCH_TOOL, CRAFTS_TOOL],
        messages=[{"role": "user", "content": "a gift under 5000"}],
    )


SPENT = httpx.Response(
    429,
    json={
        "error": {
            "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "47s"}]
        }
    },
)


async def test_a_spent_model_hands_the_question_to_the_next_one():
    rotation = ModelRotation(MODELS)
    transport, asked = scripted(
        {
            "first": SPENT,
            "second": httpx.Response(200, json=answer("Two pieces.")),
            "third": httpx.Response(200, json=answer("never reached")),
        }
    )

    with pytest.MonkeyPatch.context() as patch:
        talk = conversation(rotation, transport, patch)
        turn = await talk.next_turn()

    assert turn.text == "Two pieces."
    # Asked in order, and stopped at the one that answered.
    assert asked == ["first", "second"]


async def test_the_spent_model_is_not_asked_again_next_time():
    rotation = ModelRotation(MODELS)
    transport, asked = scripted(
        {
            "first": SPENT,
            "second": httpx.Response(200, json=answer("Two pieces.")),
            "third": httpx.Response(200, json=answer("never reached")),
        }
    )

    with pytest.MonkeyPatch.context() as patch:
        await conversation(rotation, transport, patch).next_turn()
        asked.clear()
        await conversation(rotation, transport, patch).next_turn()

    # The cooldown is on the rotation, not the request: re-learning that a
    # model is spent costs a request and the latency of making it.
    assert asked == ["second"]


async def test_when_every_model_is_spent_the_shopper_is_told():
    rotation = ModelRotation(MODELS)
    transport, asked = scripted(dict.fromkeys(MODELS, SPENT))

    with pytest.MonkeyPatch.context() as patch:
        talk = conversation(rotation, transport, patch)
        with pytest.raises(RateLimited):
            await talk.next_turn()

    # Every one tried once before giving up — and none of them waited 47s.
    assert asked == MODELS


def test_all_resting_still_offers_the_one_that_frees_up_first():
    rotation = ModelRotation(MODELS)
    rotation.rest("first", 600)
    rotation.rest("second", 60)
    rotation.rest("third", 300)

    # A refusal is worse than a long shot: the soonest to return is offered.
    assert rotation.available() == ["second"]


def test_a_rotation_needs_a_model():
    with pytest.raises(ValueError):
        ModelRotation([])


async def test_a_model_this_key_cannot_use_costs_that_model_and_not_the_answer():
    rotation = ModelRotation(MODELS)
    transport, asked = scripted(
        {
            # A name that does not exist: a typo in a deployment's list, or a
            # model this key was never given.
            "first": httpx.Response(404, json={"error": {"message": "not found"}}),
            "second": httpx.Response(200, json=answer("Two pieces.")),
            "third": httpx.Response(200, json=answer("never reached")),
        }
    )

    with pytest.MonkeyPatch.context() as patch:
        turn = await conversation(rotation, transport, patch).next_turn()

    # 404 is not retryable, and before this it escaped the rotation and failed
    # the request outright — one wrong name breaking the whole assistant.
    assert turn.text == "Two pieces."
    assert asked == ["first", "second"]


BUSY = httpx.Response(503, text="the model is busy")


async def test_a_busy_model_is_not_sidelined():
    rotation = ModelRotation(MODELS)
    transport, asked = scripted(
        {
            "first": BUSY,
            "second": httpx.Response(200, json=answer("Two pieces.")),
            "third": httpx.Response(200, json=answer("never reached")),
        }
    )

    with pytest.MonkeyPatch.context() as patch:
        await conversation(rotation, transport, patch).next_turn()

    # 503 says "not this second"; 429 says "not for a while". Resting a busy
    # model for a minute takes it out of the fleet for a whole investigation,
    # which is how a run ends up on its fifth choice with no time to answer.
    assert rotation.available() == MODELS


async def test_the_first_pass_waits_for_nobody():
    rotation = ModelRotation(MODELS)
    transport, asked = scripted(
        {
            "first": BUSY,
            "second": BUSY,
            "third": httpx.Response(200, json=answer("Two pieces.")),
        }
    )

    started = asyncio.get_running_loop().time()
    with pytest.MonkeyPatch.context() as patch:
        turn = await conversation(rotation, transport, patch).next_turn()
    elapsed = asyncio.get_running_loop().time() - started

    assert turn.text == "Two pieces."
    assert asked == ["first", "second", "third"]
    # Backing off twice before trying a neighbour would have cost six seconds.
    # Another model costs one round trip.
    assert elapsed < 0.5
