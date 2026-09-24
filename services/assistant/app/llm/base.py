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
class Photograph:
    """An image sent to the model, as bytes rather than a URL.

    A URL would make the model's host fetch whatever we named, which is an
    SSRF engine pointed at the cluster. The bytes come from the browser, are
    checked here, and go no further than the provider.
    """

    media_type: str
    data: bytes


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

    async def structured(
        self,
        *,
        system: str,
        instruction: str,
        schema: dict[str, Any],
        photograph: Photograph | None = None,
    ) -> dict[str, Any]:
        """One answer, shaped by a schema rather than by hope.

        Drafting a listing is not a conversation: it is one question with one
        answer, and the answer has to be fields a form can be filled from. Both
        providers can be told to return exactly that shape, so neither prose
        nor a fenced code block ever has to be parsed.
        """
        ...
