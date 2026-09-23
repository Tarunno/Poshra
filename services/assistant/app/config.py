"""Settings, read from the environment and validated at startup."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required")
    return value


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    catalog_url: str
    model: str
    max_tokens: int
    # A hard ceiling on how many times Claude may call a tool for one message.
    # Without it a confused turn can loop against the catalog indefinitely,
    # and every iteration costs money.
    max_tool_calls: int
    request_timeout: float

    @classmethod
    def load(cls) -> Config:
        return cls(
            anthropic_api_key=_require("ANTHROPIC_API_KEY"),
            catalog_url=_require("CATALOG_URL").rstrip("/"),
            model=os.environ.get("ASSISTANT_MODEL", "claude-opus-5"),
            max_tokens=int(os.environ.get("ASSISTANT_MAX_TOKENS", "2048")),
            max_tool_calls=int(os.environ.get("ASSISTANT_MAX_TOOL_CALLS", "6")),
            request_timeout=float(os.environ.get("CATALOG_TIMEOUT", "5")),
        )
