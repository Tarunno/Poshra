# ADR-0002: Single monorepo for all services

- **Status:** Accepted
- **Date:** 2026-09-22

## Context
Services share gRPC contracts (`proto/`), Kafka event schemas, deployment manifests and evals.
One developer owns everything.

## Decision
Keep all services, contracts, infrastructure and docs in one repository, each service with its
own toolchain and dependency file (`pyproject.toml`, `go.mod`, `package.json`).

## Consequences
- Atomic changes across a contract and its producers/consumers in one commit.
- One CI pipeline, which must use path filters so a docs change doesn't rebuild everything.
- Services stay independently buildable and deployable; the monorepo is a *source* layout,
  not a shared runtime.

## Alternatives considered
- **Polyrepo (one repo per service):** clearer ownership boundaries for large teams, but contract
  changes need coordinated multi-repo PRs and versioned packages. Overhead without benefit here.
