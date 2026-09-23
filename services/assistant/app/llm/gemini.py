"""Gemini, over its REST API.

No SDK: the surface used here is one endpoint, and a dependency that wraps one
endpoint is a dependency that breaks on its own schedule.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

import httpx

from app.llm.base import Conversation, ToolCall, ToolResult, ToolSpec, Turn

log = logging.getLogger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# A free tier is rate limited and a shared model has busy moments; neither is
# an error worth failing a shopper's question over.
RETRYABLE = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BASE_BACKOFF = 2.0

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


def _declaration(tool: ToolSpec) -> dict[str, Any]:
    declaration: dict[str, Any] = {"name": tool.name, "description": tool.description}
    parameters = _clean_schema(tool.parameters)
    # A tool that takes nothing must omit parameters entirely; an empty
    # properties object is rejected.
    if parameters.get("properties"):
        declaration["parameters"] = parameters
    return declaration


class RateLimited(RuntimeError):
    """The model is busy and retrying did not clear it."""


class GeminiConversation:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_tokens: int,
        timeout: float,
        system: str,
        tools: Sequence[ToolSpec],
        messages: Sequence[dict[str, str]],
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout
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

        return self._read(await self._post(payload))

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send one request, waiting out the answers that mean "not now"."""
        backoff = BASE_BACKOFF
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                response = await client.post(
                    f"{BASE_URL}/models/{self._model}:generateContent",
                    headers={"x-goog-api-key": self._api_key},
                    json=payload,
                )
                if response.status_code not in RETRYABLE:
                    response.raise_for_status()
                    return response.json()

                if attempt == MAX_ATTEMPTS:
                    log.error(
                        "gemini still unavailable after retrying",
                        extra={"status": response.status_code, "attempts": attempt},
                    )
                    raise RateLimited(
                        f"the model answered {response.status_code} {MAX_ATTEMPTS} times"
                    )

                # Google says how long to wait when it knows; otherwise back
                # off, because hammering a rate limit is how you stay in it.
                wait = _retry_after(response) or backoff
                log.warning(
                    "gemini busy, waiting",
                    extra={"status": response.status_code, "wait": wait, "attempt": attempt},
                )
                await asyncio.sleep(wait)
                backoff *= 2

        raise RateLimited("unreachable")

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

    def __init__(self, api_key: str, model: str, max_tokens: int, timeout: float) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout

    def start(
        self,
        *,
        system: str,
        tools: Sequence[ToolSpec],
        messages: Sequence[dict[str, str]],
    ) -> Conversation:
        return GeminiConversation(
            api_key=self._api_key,
            model=self._model,
            max_tokens=self._max_tokens,
            timeout=self._timeout,
            system=system,
            tools=tools,
            messages=messages,
        )
