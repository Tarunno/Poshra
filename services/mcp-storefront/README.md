# mcp-storefront (Python)

Poshra's storefront as a remote [MCP](https://modelcontextprotocol.io) server, so an
AI agent can shop the catalog without anything about Poshra being written into
the agent. It connects, asks what tools exist, and gets the names, the argument
schemas and the prose describing when to use each one.

## What is here

Three read-only tools, over Streamable HTTP at `POST /mcp`:

| Tool | Takes | Gives back |
| --- | --- | --- |
| `search_products` | query, craft, division, price bounds, in-stock | up to 8 pieces, flattened |
| `list_crafts` | — | every craft with the slug `search_products` wants |
| `get_product` | slug | one piece, with its full description |

Each publishes an **output** schema as well as an input one, so a client knows
the shape of the answer before it calls and receives it as `structuredContent`
beside the text. Each is annotated `readOnlyHint`, which is how a host decides
what may run without asking a human.

The cart and checkout tools are not here yet — see the plan below.

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

1. Cart tools (`view_cart`, `add_to_cart`, `prepare_checkout`), with a scoped
   bearer token a shopper generates in their account settings. The boundary
   holds: an agent may fill a cart and may never spend money — `prepare_checkout`
   totals it and hands over to the checkout page, where a person pays.
2. Resources (`poshra://craft/{slug}`) and prompt templates.
3. Deployment: Kong route, NetworkPolicy, Argo.
4. The Poshra assistant becoming a client of this server, so the tool
   definitions live in one place instead of two.
