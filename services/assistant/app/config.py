"""Settings, read from the environment and validated at startup."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


# Each provider brings its own key and its own sensible models. Naming them
# here keeps the choice a deployment decision rather than a code change.
#
# Gemini gets a list, in preference order. The free tier is metered per model,
# so a spent quota on the first is not a spent quota on the second, and the
# assistant keeps answering by falling down the list rather than failing. They
# are named explicitly rather than through a "-latest" alias: an alias changes
# the model underneath a running deployment, and the first sign of it is an
# assistant that answers differently one morning with no commit to blame.
PROVIDERS = {
    "gemini": (
        "GEMINI_API_KEY",
        ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"),
    ),
    "anthropic": ("ANTHROPIC_API_KEY", ("claude-opus-5",)),
}


def _models(raw: str) -> tuple[str, ...]:
    """ASSISTANT_MODEL as a comma-separated list, so one name still works."""
    return tuple(name.strip() for name in raw.split(",") if name.strip())


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required")
    return value


@dataclass(frozen=True)
class Config:
    provider: str
    api_key: str
    # In preference order; the first that is not rate limited answers.
    models: tuple[str, ...]
    catalog_url: str
    checkout_url: str
    max_tokens: int
    # A hard ceiling on how many times the model may call a tool for one
    # message. Without it a confused turn can loop against the catalog
    # indefinitely, and every iteration costs money.
    max_tool_calls: int
    request_timeout: float
    llm_timeout: float

    @classmethod
    def load(cls) -> Config:
        provider = os.environ.get("LLM_PROVIDER", "gemini").strip().lower()
        if provider not in PROVIDERS:
            raise ConfigError(f"LLM_PROVIDER must be one of {sorted(PROVIDERS)}, got {provider!r}")
        key_name, default_models = PROVIDERS[provider]
        models = _models(os.environ.get("ASSISTANT_MODEL", "")) or default_models

        return cls(
            provider=provider,
            api_key=_require(key_name),
            models=models,
            catalog_url=_require("CATALOG_URL").rstrip("/"),
            # Through the gateway, so the shopper's cookie is verified there
            # exactly as it is for the storefront.
            checkout_url=_require("CHECKOUT_URL").rstrip("/"),
            max_tokens=int(os.environ.get("ASSISTANT_MAX_TOKENS", "2048")),
            max_tool_calls=int(os.environ.get("ASSISTANT_MAX_TOOL_CALLS", "6")),
            request_timeout=float(os.environ.get("CATALOG_TIMEOUT", "5")),
            # A tool-using turn takes a while; the gateway allows ninety
            # seconds, so this stays inside that.
            llm_timeout=float(os.environ.get("LLM_TIMEOUT", "60")),
        )
