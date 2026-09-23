"""Claude, through the official SDK."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from anthropic import AsyncAnthropic

from app.llm.base import Conversation, ToolCall, ToolResult, ToolSpec, Turn


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


class AnthropicProvider:
    name = "anthropic"

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
