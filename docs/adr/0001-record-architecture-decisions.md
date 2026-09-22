# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-09-22

## Context
Poshra spans five services in three languages. Without a record, the *why* behind choices is lost
and cannot be explained later to reviewers or future contributors.

## Decision
Use lightweight ADRs (Michael Nygard format) in `docs/adr/`, numbered and never deleted.
A reversed decision gets a new ADR that supersedes the old one.

## Consequences
- Every non-trivial choice costs ~10 minutes of writing.
- The repo documents its own reasoning, so decisions can be revisited with full context.
