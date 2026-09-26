"""Settings, read from the environment and validated at startup."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


class ConfigError(RuntimeError):
    pass


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required")
    return value


def _list(name: str) -> list[str]:
    return [part.strip() for part in os.environ.get(name, "").split(",") if part.strip()]


@dataclass(frozen=True)
class Config:
    catalog_url: str
    # Through the gateway, so the shopper's own token is verified there exactly
    # as it is for the storefront. Empty turns the cart tools off entirely.
    checkout_url: str
    # Where a person finishes an order. The model never takes money; it hands
    # over to this page, so the URL must be the browser's, not the cluster's.
    storefront_url: str
    request_timeout: float
    # The transport refuses a request whose Host or Origin it does not
    # recognise. That is not decoration: an MCP server is a URL a browser on
    # the same machine can also reach, so without this a page on another site
    # could drive somebody's agent through their own network. Behind the
    # gateway the Host is the gateway's, so it has to be named here.
    allowed_hosts: list[str] = field(default_factory=list)
    allowed_origins: list[str] = field(default_factory=list)

    @classmethod
    def load(cls) -> Config:
        return cls(
            catalog_url=_require("CATALOG_URL").rstrip("/"),
            checkout_url=os.environ.get("CHECKOUT_URL", "").strip().rstrip("/"),
            storefront_url=os.environ.get("STOREFRONT_URL", "").strip().rstrip("/"),
            request_timeout=float(os.environ.get("CATALOG_TIMEOUT", "5")),
            allowed_hosts=_list("MCP_ALLOWED_HOSTS"),
            allowed_origins=_list("MCP_ALLOWED_ORIGINS"),
        )
