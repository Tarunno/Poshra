# Poshra: engineering guide

## Architecture
Monorepo of independently deployable services behind Kong. See `README.md` for the layout and
`docs/adr/` for decisions. Services never read another service's database; they use its API
(REST/gRPC) or its events (Kafka).

## Conventions
- Kafka topics: `poshra.<domain>.<event>.v<N>` (e.g. `poshra.orders.created.v1`)
- Protobuf packages: `poshra.<service>.v<N>`; contracts live in `proto/` and are checked with `buf`
- Kubernetes namespace: `poshra`; regions: `ap-south`, `eu-west`
- Go modules: `github.com/Tarunno/Poshra/services/<name>`
- Money: integer minor units + ISO 4217 currency code, never floats
- IDs: UUIDv7
- Commits: Conventional Commits (`feat(checkout): ...`)
- Significant decisions are recorded as ADRs in `docs/adr/` using `0000-template.md`
