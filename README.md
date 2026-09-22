# Poshra

> An agent-ready marketplace that connects Bangladeshi artisans to buyers worldwide.
> AI turns a photo and a Bangla voice note into a sellable listing, and lets buyers
> and AI agents find authentic crafts through conversation.

*Poshra (পসরা) is the array of goods a village trader lays out for sale: many kinds of craft, one display.*

## Status

🚧 Early development. See [docs/adr](docs/adr) for design decisions.

## Repository layout

| Path | What lives here |
|---|---|
| `apps/web` | Next.js + shadcn/ui storefront and artisan dashboard |
| `services/marketplace` | Django: accounts, artisans, catalog, orders (system of record) |
| `services/checkout` | Go: checkout orchestration (gRPC client, outbox → Kafka) |
| `services/inventory` | Go: stock reservation (gRPC server) |
| `services/assistant` | Python: Claude-powered shopping assistant and listing generation |
| `services/mcp-storefront` | Python: MCP server exposing the storefront to AI agents |
| `proto` | gRPC contracts shared between services |
| `gateway/kong` | Kong declarative config and custom Lua plugins |
| `deploy` | Docker Compose (local) and Kubernetes manifests (per region) |
| `observability` | OpenTelemetry Collector, Prometheus, Grafana, Tempo, Loki config |
| `evals` | AI evaluation datasets, graders and runner |
| `docs` | Architecture decision records and architecture diagrams |
