"""What the assistant needs from a language model, and nothing more.

The shape of a tool-using conversation is the same everywhere: send the tools,
the model asks to call one, you run it and send the result back, repeat until
it answers. Only the wire format differs — Anthropic calls it a tool_use block,
Gemini calls it a functionCall — so that difference is all a provider has to
absorb.

Deliberately not a lowest-common-denominator chat API. The loop that decides
how many tool calls are affordable, what a failing tool means, and which pieces
the answer rests on stays in one place; a provider only converts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolSpec:
    """A tool, described once, in JSON Schema every provider understands."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    # Anthropic gives each call an id; Gemini does not, so one is invented
    # there. Either way the loop needs something to match a result to a call.
    id: str = ""


@dataclass(frozen=True)
class ToolResult:
    call: ToolCall
    content: Any


@dataclass(frozen=True)
class Turn:
    """One answer from the model: either it spoke, or it asked for tools."""

    text: str = ""
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class Conversation(Protocol):
    """One request's exchange. The provider keeps the history in its own shape."""

    async def next_turn(self) -> Turn: ...

    def add_tool_results(self, results: Sequence[ToolResult]) -> None: ...


class Provider(Protocol):
    name: str

    def start(
        self,
        *,
        system: str,
        tools: Sequence[ToolSpec],
        messages: Sequence[dict[str, str]],
    ) -> Conversation: ...
