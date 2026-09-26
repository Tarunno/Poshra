# mcp-storefront (Python)

Poshra's storefront as a remote [MCP](https://modelcontextprotocol.io) server, so an
AI agent can shop the catalog without anything about Poshra being written into
the agent. It connects, asks what tools exist, and gets the names, the argument
schemas and the prose describing when to use each one.

## What is here

Over Streamable HTTP at `POST /mcp`. Six tools, in two halves:

| Tool | Needs a shopper | Gives back |
| --- | --- | --- |
| `search_products` | no | up to 8 pieces, flattened |
| `list_crafts` | no | every craft with the slug `search_products` wants |
| `get_product` | no | one piece, with its full description |
| `view_cart` | yes | the basket and its total |
| `add_to_cart` | yes | what went in, and the basket after |
| `prepare_checkout` | yes | the total, and a link to the page where a **person** pays |

**An agent may fill a basket and may never spend money.** `prepare_checkout`
returns `charged: false` and a URL; the paying happens on that page, by a
human. That is the one sentence this service exists to keep true.

The read tools need nobody, so an agent with no token browses exactly what an
anonymous visitor can. Without a `CHECKOUT_URL` the cart tools are not
registered at all — three tools rather than six that fail.

Every tool publishes an **output** schema as well as an input one, so a client
knows the shape of the answer before it calls and receives it as
`structuredContent` beside the text. Each carries annotations (`readOnlyHint`,
`destructiveHint`), which is how a host decides what may run without asking a
human — filling a basket is reversible and charges nothing, so it must not
trip that prompt.

### Resources and prompts

Both of the things most MCP servers skip, because the distinction they draw is
the interesting part: a **tool** is reached for by the *model*, a **resource**
is attached by the *application*, and a **prompt** is chosen by the *user*.

- `poshra://crafts` and `poshra://product/{slug}` — the same catalogue as
  context rather than as a call, for a host that already knows what the
  shopper is looking at.
- `find_a_gift` and `about_this_craft` — the openings people actually arrive
  with, written once so every agent asks them the same way.

## Authentication

A shopper mints a token at `/dashboard/agents` and pastes it into their agent,
which sends it as `Authorization: Bearer …`. It is an ordinary Poshra JWT, so
**Kong verifies it with no special case** and injects the identity every
service already understands. Two claims set it apart: `scope: agent`, and a
`jti` naming a row the shopper can revoke.

Revocation is the interesting problem. The gateway can check a signature
without asking anybody — which is what makes it fast, and exactly why it
cannot know the token was withdrawn an hour ago. So the tools that act on
somebody's behalf ask the marketplace and cache the answer for a minute, and
the tools that only read the public catalogue do not ask at all. Revocation is
immediate for the operations that can cause harm and irrelevant for the ones
that cannot.

The MCP spec's own answer is OAuth 2.1 with dynamic client registration, so a
client discovers everything from the URL alone. We deferred it: see
`docs/adr/` for what that costs.

## How it fits

This service owns no database. It is a protocol adapter: MCP outward, the same
marketplace REST API the web storefront uses inward. The gateway in front of it
supplies identity and rate limiting, exactly as it does for every other route.

```
agent ──JSON-RPC over HTTP──▶ Kong /mcp ──▶ mcp-storefront ──REST──▶ marketplace
```

The transport is **stateless**: every request carries what it needs, so any
replica can answer any call and a restart costs nobody their session. The cost
is that the server cannot push notifications between calls, which a catalog
nobody subscribes to does not need.

## Configuration

| Variable | Meaning |
| --- | --- |
| `CATALOG_URL` | marketplace API base, e.g. `http://kong-proxy/internal/marketplace` |
| `CHECKOUT_URL` | cart API through the **public** route; unset turns the cart tools off |
| `STOREFRONT_URL` | the browser-facing base, used for the checkout hand-off link |
| `CATALOG_TIMEOUT` | seconds per upstream call, default 5 |
| `MCP_ALLOWED_HOSTS` | comma-separated Host values the transport will answer |
| `MCP_ALLOWED_ORIGINS` | comma-separated Origins allowed to reach it from a browser |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | collector; tracing is off when unset |

Leaving both `MCP_ALLOWED_*` empty turns DNS-rebinding protection off. That is
right behind the gateway, which is the only way in, and wrong anywhere a
browser can reach the port directly.

## Running it

    uv sync
    uv run pytest
    CATALOG_URL=http://192.168.110.201/api/marketplace \
      uv run uvicorn app.main:app --port 8900

Then talk to it:

    curl -s http://127.0.0.1:8900/mcp \
      -H 'Content-Type: application/json' \
      -H 'Accept: application/json, text/event-stream' \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

## Still to come

The Poshra assistant (`services/assistant`) defines its own copy of these
tools and calls the catalogue directly. Pointing it at this server instead
would leave one definition with two consumers, and is the obvious next step.
