# ADR-0003: Kong Gateway OSS (DB-less) as the API gateway

- **Status:** Accepted
- **Date:** 2026-09-22

## Context
Every external request (browser, AI agents via MCP) needs the same cross-cutting handling:
authentication, rate limiting, request IDs, tracing and routing to the right service. Implementing
these in each service would duplicate logic in three languages. Poshra also needs custom edge
logic (per-user LLM token budgets), so the gateway must be extensible.

## Decision
Use **Kong Gateway OSS 3.9** in **DB-less mode**, configured by a declarative file
(`gateway/kong/kong.yaml`) kept in git. Kong is the only component exposed to clients;
services are reachable only on the internal network. Custom behaviour is written as Lua plugins.

## Consequences
- One place to change edge policy; services stay focused on business logic.
- Gateway configuration is versioned and reviewed like code; no gateway database to run.
- DB-less mode means config changes are applied by reloading the whole file (`POST /config`),
  and Admin API writes to individual entities are not available.
- The open-source `kong` image is not published beyond 3.9.x; newer versions ship as
  `kong/kong-gateway`. We accept staying on 3.9 for now. Revisit if a security fix or needed
  feature is unavailable: options are the `kong/kong-gateway` image in free mode, or migrating
  to Envoy Gateway.
- Some plugins (OIDC, advanced rate limiting) are Enterprise-only; the design uses OSS plugins
  plus custom Lua where needed.

## Alternatives considered
- **Envoy / Envoy Gateway:** strong ecosystem and Gateway API support, but custom logic means
  Lua or WASM filters with a steeper path; weaker fit for quick custom plugins.
- **Traefik:** simple, good k8s integration; plugin model (Yaegi Go) is less mature for this use.
- **Auth and rate limiting inside each service:** no extra hop, but duplicated in Django, Go and
  Python, and inconsistent over time.
