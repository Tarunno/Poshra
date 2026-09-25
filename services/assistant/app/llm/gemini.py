"""Gemini, over its REST API.

No SDK: the surface used here is one endpoint, and a dependency that wraps one
endpoint is a dependency that breaks on its own schedule.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from collections.abc import Sequence
from typing import Any

import httpx

from app.llm.base import (
    Conversation,
    Photograph,
    Recording,
    ToolCall,
    ToolResult,
    ToolSpec,
    Turn,
)

log = logging.getLogger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# A free tier is rate limited and a shared model has busy moments; neither is
# an error worth failing a shopper's question over.
RETRYABLE = {429, 500, 502, 503, 504}
# A name this key cannot use. Not an error to fail a shopper over either: the
# rest of the list is still good, and one wrong name in a deployment's
# configuration should cost that model, not the assistant.
UNKNOWN_MODEL = 404
MAX_ATTEMPTS = 4
BASE_BACKOFF = 2.0
# Past this, waiting is worse than answering. A busy moment clears in a second
# or two; when Google says "come back in 47 seconds" it means the quota is
# spent, and holding someone's request open for that long only turns a clear
# "try again shortly" into a page that appears to have frozen.
MAX_WAIT = 8.0
# How long a model is left alone once it has said no. Google's RetryInfo is
# honoured when it asks for longer; this is the floor, because a model that
# refused a second ago will refuse again and each attempt costs a request and
# the latency of making it.
MIN_COOLDOWN = 60.0
# A model that does not exist will not exist in a minute either. Long enough
# that a misconfigured name is paid for once, short enough that access granted
# later is picked up without a restart.
MISSING_COOLDOWN = 3600.0

# Gemini accepts a subset of JSON Schema and rejects the rest outright, so the
# schemas written for Anthropic are trimmed rather than sent as they are.
ALLOWED_SCHEMA_KEYS = {
    "type",
    "description",
    "enum",
    "items",
    "properties",
    "required",
    "nullable",
}


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in schema.items():
        if key not in ALLOWED_SCHEMA_KEYS:
            continue  # additionalProperties and friends are refused
        if key == "properties" and isinstance(value, dict):
            cleaned[key] = {name: _clean_schema(sub) for name, sub in value.items()}
        elif key == "items" and isinstance(value, dict):
            cleaned[key] = _clean_schema(value)
        else:
            cleaned[key] = value
    return cleaned


def _response_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """The same trimming a tool's parameters get: this endpoint is as fussy."""
    return _clean_schema(schema)


def _declaration(tool: ToolSpec) -> dict[str, Any]:
    declaration: dict[str, Any] = {"name": tool.name, "description": tool.description}
    parameters = _clean_schema(tool.parameters)
    # A tool that takes nothing must omit parameters entirely; an empty
    # properties object is rejected.
    if parameters.get("properties"):
        declaration["parameters"] = parameters
    return declaration


class DraftFailed(RuntimeError):
    """The model answered, but not with the fields that were asked for."""


class RateLimited(RuntimeError):
    """Every model is busy and retrying did not clear it."""


class _ModelUnavailable(Exception):
    """One model said no. Another may not."""

    def __init__(self, message: str, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ModelRotation:
    """Which model to ask next, and which ones are still sulking.

    The free tier is metered per model, so one that has spent its quota says so
    while its neighbours are still answering. Rather than failing the shopper,
    the request falls down the list; the model that refused is set aside for a
    while so later requests skip it instead of re-learning it is spent.

    The state is per process, on purpose. Sharing it between replicas would
    mean Redis, a schema and a failure mode of its own, to save each replica
    one wasted request per model per cooldown. The clock is monotonic so a
    cooldown survives the system clock moving.
    """

    def __init__(self, models: Sequence[str]) -> None:
        if not models:
            raise ValueError("at least one model is required")
        self._models = tuple(models)
        self._resting: dict[str, float] = {}

    def available(self) -> list[str]:
        """Preference order, skipping anything still cooling off."""
        now = time.monotonic()
        ready = [model for model in self._models if self._resting.get(model, 0.0) <= now]
        # All of them spent: try the one that frees up first, so a shopper gets
        # an answer rather than a refusal the moment any quota returns.
        return ready or [min(self._models, key=lambda m: self._resting.get(m, 0.0))]

    def rest(self, model: str, seconds: float) -> None:
        self._resting[model] = time.monotonic() + max(seconds, MIN_COOLDOWN)


class GeminiEndpoint:
    """generateContent, with the model rotation in front of it.

    A conversation and a one-shot draft are different questions, but the same
    wire call and the same quota, so the falling-down-the-list lives here
    rather than in either of them.
    """

    def __init__(self, api_key: str, rotation: ModelRotation, timeout: float) -> None:
        self._api_key = api_key
        self._rotation = rotation
        self._timeout = timeout
        # Which model actually answered. Attributed so a change in how the
        # assistant writes can be traced to the model that wrote it.
        self.answered_by: str | None = None

    async def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Ask each model in turn until one answers."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            refusals: list[str] = []
            for model in self._rotation.available():
                try:
                    body = await self._ask(client, model, payload)
                except _ModelUnavailable as refusal:
                    # Set it aside and try the next one. Nothing is waited out
                    # here: the whole point of a second model is not waiting.
                    self._rotation.rest(model, refusal.retry_after)
                    refusals.append(f"{model}: {refusal}")
                    continue
                # The answer has to be attributed, or a change in how the
                # assistant writes cannot be traced to which model wrote it.
                self.answered_by = model
                return body

        log.error("every gemini model refused", extra={"refusals": refusals})
        raise RateLimited("; ".join(refusals))

    async def _ask(
        self, client: httpx.AsyncClient, model: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """One model, waiting out the answers that mean "not just now"."""
        backoff = BASE_BACKOFF
        for attempt in range(1, MAX_ATTEMPTS + 1):
            response = await client.post(
                f"{BASE_URL}/models/{model}:generateContent",
                headers={"x-goog-api-key": self._api_key},
                json=payload,
            )
            if response.status_code == UNKNOWN_MODEL:
                log.error(
                    "gemini does not know this model",
                    extra={"model": model, "body": response.text[:200]},
                )
                raise _ModelUnavailable("unknown to this key", MISSING_COOLDOWN)

            if response.status_code not in RETRYABLE:
                response.raise_for_status()
                return response.json()

            # Google says how long to wait when it knows; otherwise back off,
            # because hammering a rate limit is how you stay in it.
            wait = _retry_after(response) or backoff

            if attempt == MAX_ATTEMPTS:
                raise _ModelUnavailable(
                    f"answered {response.status_code} {MAX_ATTEMPTS} times", wait
                )
            if wait > MAX_WAIT:
                # "Come back in 47 seconds" means the quota is spent, not that
                # the model is momentarily busy. Waiting turns a clear "try
                # again shortly" into a page that appears to have frozen, so
                # the next model gets the question instead.
                raise _ModelUnavailable(f"asked for {wait:.0f}s", wait)

            log.warning(
                "gemini busy, waiting",
                extra={
                    "model": model,
                    "status": response.status_code,
                    "wait": wait,
                    "attempt": attempt,
                },
            )
            await asyncio.sleep(wait)
            backoff *= 2

        raise _ModelUnavailable("unreachable", MIN_COOLDOWN)


class GeminiConversation:
    def __init__(
        self,
        *,
        endpoint: GeminiEndpoint,
        max_tokens: int,
        system: str,
        tools: Sequence[ToolSpec],
        messages: Sequence[dict[str, str]],
    ) -> None:
        self._endpoint = endpoint
        self._max_tokens = max_tokens
        self._system = system
        self._tools = [_declaration(tool) for tool in tools]
        # Gemini names the assistant "model"; everything else is "user".
        self._contents: list[dict[str, Any]] = [
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [{"text": message["content"]}],
            }
            for message in messages
        ]

    async def next_turn(self) -> Turn:
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": self._system}]},
            "contents": self._contents,
            "generationConfig": {"maxOutputTokens": self._max_tokens},
        }
        if self._tools:
            payload["tools"] = [{"functionDeclarations": self._tools}]

        return self._read(await self._endpoint.generate(payload))

    def _read(self, body: dict[str, Any]) -> Turn:
        candidates = body.get("candidates") or []
        if not candidates:
            # A prompt can be blocked outright, in which case there is no
            # candidate at all rather than an empty one.
            log.warning("gemini returned no candidate", extra={"body": str(body)[:300]})
            return Turn(text="")

        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []

        texts: list[str] = []
        calls: list[ToolCall] = []
        for index, part in enumerate(parts):
            if "functionCall" in part:
                call = part["functionCall"]
                calls.append(
                    ToolCall(
                        name=call.get("name", ""),
                        arguments=call.get("args") or {},
                        # Gemini has no call id; results are matched by name,
                        # so one is invented to keep the loop uniform.
                        id=f"{call.get('name', 'call')}-{index}",
                    )
                )
            elif "text" in part:
                texts.append(part["text"])

        # The turn has to be remembered, or the next request forgets it asked.
        if parts:
            self._contents.append({"role": "model", "parts": parts})

        return Turn(text="\n".join(texts).strip(), tool_calls=tuple(calls))

    def add_message(self, text: str) -> None:
        self._contents.append({"role": "user", "parts": [{"text": text}]})

    def add_tool_results(self, results: Sequence[ToolResult]) -> None:
        self._contents.append(
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": result.call.name,
                            # Gemini expects an object, so a bare list or
                            # string is wrapped rather than sent as it is.
                            "response": _as_object(result.content),
                        }
                    }
                    for result in results
                ],
            }
        )


def _retry_after(response: httpx.Response) -> float | None:
    """Seconds Google asked us to wait, if it said."""
    header = response.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            return None
    # The JSON error carries a RetryInfo with a duration like "37s".
    try:
        for detail in response.json().get("error", {}).get("details", []):
            delay = detail.get("retryDelay")
            if isinstance(delay, str) and delay.endswith("s"):
                return float(delay[:-1])
    except Exception:  # noqa: BLE001 — a malformed error body is not our problem
        return None
    return None


def _as_object(content: Any) -> dict[str, Any]:
    return content if isinstance(content, dict) else {"result": content}


class GeminiProvider:
    name = "gemini"
    # Gemini takes audio inline, in the containers a browser records: webm,
    # ogg, mp4 and wav were all accepted against the live API before this was
    # written, so nothing is transcoded on the way.
    accepts_audio = True

    def __init__(
        self, api_key: str, models: Sequence[str], max_tokens: int, timeout: float
    ) -> None:
        # Held here, not on the conversation: a model found to be spent must
        # stay skipped for the requests that follow, not just this one.
        self._endpoint = GeminiEndpoint(api_key, ModelRotation(models), timeout)
        self._max_tokens = max_tokens

    def start(
        self,
        *,
        system: str,
        tools: Sequence[ToolSpec],
        messages: Sequence[dict[str, str]],
    ) -> Conversation:
        return GeminiConversation(
            endpoint=self._endpoint,
            max_tokens=self._max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )

    async def structured(
        self,
        *,
        system: str,
        instruction: str,
        schema: dict[str, Any],
        photograph: Photograph | None = None,
        recording: Recording | None = None,
    ) -> dict[str, Any]:
        """One answer, in the shape the schema asks for.

        responseSchema is the point: the model is constrained to the fields a
        listing form has, so nothing here parses prose or strips a fenced code
        block and hopes. A missing field is then a model that had nothing to
        say about it, not a parser that lost it.
        """
        parts: list[dict[str, Any]] = [{"text": instruction}]
        if recording is not None:
            parts.insert(
                0,
                {
                    "inlineData": {
                        "mimeType": recording.media_type,
                        "data": base64.b64encode(recording.data).decode(),
                    }
                },
            )
        if photograph is not None:
            # The image goes first: the model reads it as the subject of the
            # instruction that follows rather than as an afterthought.
            parts.insert(
                0,
                {
                    "inlineData": {
                        "mimeType": photograph.media_type,
                        "data": base64.b64encode(photograph.data).decode(),
                    }
                },
            )

        body = await self._endpoint.generate(
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": {
                    "maxOutputTokens": self._max_tokens,
                    "responseMimeType": "application/json",
                    "responseSchema": _response_schema(schema),
                },
            }
        )

        candidates = body.get("candidates") or []
        if not candidates:
            log.warning("gemini drafted nothing", extra={"body": str(body)[:300]})
            raise DraftFailed("the model returned no answer")

        text = "".join(
            part.get("text", "") for part in (candidates[0].get("content") or {}).get("parts") or []
        ).strip()
        try:
            drafted = json.loads(text)
        except json.JSONDecodeError as error:
            # With responseSchema set this should not happen; if it does, the
            # half-written JSON is worth seeing rather than guessing at.
            log.error("gemini json was not json", extra={"text": text[:300]})
            raise DraftFailed("the model's answer was not the shape asked for") from error

        if not isinstance(drafted, dict):
            raise DraftFailed("the model answered with something other than fields")
        return drafted
