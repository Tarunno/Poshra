"""Claude, through the official SDK."""

from __future__ import annotations

import base64
from collections.abc import Sequence
from typing import Any

from anthropic import AsyncAnthropic

from app.llm.base import (
    Conversation,
    Photograph,
    Recording,
    TextDelta,
    ToolCall,
    ToolResult,
    ToolSpec,
    Turn,
)

# Claude has no response-schema setting. The equivalent is a tool it is forced
# to call: the arguments are validated against the schema for the same reason,
# and the answer arrives as fields rather than as prose to be picked apart.
DRAFT_TOOL = "record_listing"


class AnthropicConversation:
    def __init__(
        self,
        *,
        client: Any,
        model: str,
        max_tokens: int,
        system: str,
        tools: Sequence[ToolSpec],
        messages: Sequence[dict[str, str]],
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._system = system
        self._tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in tools
        ]
        self._messages: list[dict[str, Any]] = [dict(message) for message in messages]
        self._last_call_blocks: list[Any] = []

    async def next_turn(self) -> Turn:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=self._system,
            tools=self._tools,
            messages=self._messages,
        )

        texts = [block.text for block in response.content if block.type == "text"]
        calls = [
            ToolCall(
                name=block.name,
                arguments=block.input if isinstance(block.input, dict) else {},
                id=block.id,
            )
            for block in response.content
            if block.type == "tool_use"
        ]

        if calls:
            # The assistant turn has to go back verbatim, or the tool results
            # have nothing to answer.
            self._messages.append({"role": "assistant", "content": response.content})

        return Turn(text="\n".join(texts).strip(), tool_calls=tuple(calls))

    def add_message(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})

    async def stream_turn(self):
        """Not streamed here, only shaped like it.

        Claude can stream, but this deployment has never had credit on it and
        an untested streaming path is worse than an honest buffered one. The
        answer arrives in a single piece, which the caller cannot tell from a
        very fast model.
        """
        turn = await self.next_turn()
        if turn.text:
            yield TextDelta(turn.text)
        yield turn

    def add_tool_results(self, results: Sequence[ToolResult]) -> None:
        import json

        # Every result in one user message: splitting them teaches the model to
        # stop asking for several things at once.
        self._messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": result.call.id,
                        "content": json.dumps(result.content),
                    }
                    for result in results
                ],
            }
        )


class CannotHear(RuntimeError):
    """This provider was given a recording it has no way to listen to."""


class AnthropicProvider:
    name = "anthropic"
    # Claude reads images but not audio. Said plainly here so the drafter can
    # tell an artisan to type instead, rather than quietly dropping what she
    # said and drafting from the photograph alone.
    accepts_audio = False

    def __init__(
        self, api_key: str, model: str, max_tokens: int, client: Any | None = None
    ) -> None:
        self._client = client or AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def start(
        self,
        *,
        system: str,
        tools: Sequence[ToolSpec],
        messages: Sequence[dict[str, str]],
    ) -> Conversation:
        return AnthropicConversation(
            client=self._client,
            model=self._model,
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
        if recording is not None:
            raise CannotHear("claude cannot be given a recording")

        content: list[dict[str, Any]] = []
        if photograph is not None:
            # First, so the instruction reads as being about this picture.
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": photograph.media_type,
                        "data": base64.b64encode(photograph.data).decode(),
                    },
                }
            )
        content.append({"type": "text", "text": instruction})

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            tools=[
                {
                    "name": DRAFT_TOOL,
                    "description": "Record the drafted listing.",
                    "input_schema": schema,
                }
            ],
            # Not a suggestion: the only acceptable answer is the fields.
            tool_choice={"type": "tool", "name": DRAFT_TOOL},
            messages=[{"role": "user", "content": content}],
        )

        for block in response.content:
            if block.type == "tool_use" and isinstance(block.input, dict):
                return block.input
        raise RuntimeError("claude answered without the fields it was asked for")
