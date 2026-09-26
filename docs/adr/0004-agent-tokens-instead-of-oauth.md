# ADR-0004: Bearer tokens for MCP agents, not OAuth 2.1

- **Status:** Accepted
- **Date:** 2026-09-26

## Context

`services/mcp-storefront` exposes Poshra's catalogue and basket over the Model
Context Protocol, so an AI agent can shop on a customer's behalf. Three of its
six tools act for a person and therefore need to know which person.

The MCP specification is unambiguous about how an HTTP-transport server should
answer that. The server is an OAuth 2.1 **resource server**: an unauthenticated
call returns `401` with a `WWW-Authenticate` header pointing at protected
resource metadata (RFC 9728); the client follows that to the authorization
server's own metadata (RFC 8414); it registers itself dynamically (RFC 7591);
it runs authorization code with PKCE; and it names the resource it wants a
token for (RFC 8707) so the token is audience-bound and cannot be replayed
against a different server.

The point of all that discovery is that nothing is configured by hand. A person
pastes a URL into their agent and everything else is negotiated.

Poshra has no authorization server. It has a Django service that signs RS256
access tokens for its own browser sessions, and a gateway that verifies them.

## Decision

A shopper mints a **scoped bearer token** at `/dashboard/agents` and pastes it
into their agent, which sends it as `Authorization: Bearer …`.

The token is an ordinary Poshra JWT — same issuer, same audience, same signing
key — so the gateway verifies it with no special case and injects the identity
headers every service already trusts. Two claims set it apart: `scope: agent`,
and a `jti` naming a row in `accounts_agent_token` that the shopper can list
and revoke.

Revocation is enforced by the tools that act on somebody's behalf, not by the
gateway. The gateway checks a signature without asking anybody, which is what
makes it fast and exactly why it cannot know the row behind the token was
withdrawn. So `view_cart`, `add_to_cart` and `prepare_checkout` ask the
marketplace whether the `jti` is still live, and cache the answer for a minute;
the read-only tools, which serve the same catalogue an anonymous visitor
browses, never ask.

## Consequences

**Easier.** No authorization server to run, and no new verification path: the
gateway does the same thing for an agent that it does for a browser, so there
is one place where a Poshra token is checked rather than two that can drift.
Because the token is ours and issued for our own audience, the confused-deputy
problem the spec's resource indicators exist to prevent does not arise — there
is nowhere else to replay it. The shopper can see every token they have made,
when it was last used, and revoke it.

**Harder.** The paste-a-URL-and-it-works flow is gone; a person has to visit
their settings, mint a token and copy it into their agent. An MCP client that
expects the discovery dance gets a plain `401` with no metadata to follow, so
it cannot recover on its own. And revocation is immediate only for the
operations that can cause harm: a revoked token can still read the public
catalogue for up to a minute, which is a thing an anonymous agent could do
anyway.

**To watch.** Token lifetime is thirty days, chosen because an agent has nobody
to refresh it; that is a long time for a credential sitting in a config file on
somebody's laptop, and it is bounded only by the shopper noticing. If hosts
start expecting OAuth discovery as a matter of course, this becomes the reason
Poshra does not appear in their directories.

## Alternatives considered

**Full OAuth 2.1 with dynamic client registration.** What the spec asks for,
and what we would do with more time. It means running an authorization server
with consent screens, client registration, PKCE and token rotation — a real
component, and a larger security surface than everything else in this
repository put together. Deferred, not rejected.

**Opaque tokens checked at the gateway.** Revocable the moment they are
revoked, because every request is a lookup. It needs shared state at the edge:
the gateway plugin would have to reach Redis on every call, which turns a
signature check into a network round trip on the hot path of every route, not
just this one.

**Long-lived JWT with no revocation at all.** The simplest thing, and the
reason it lost is that a credential a person hands to third-party software has
to be withdrawable. A token you cannot take back is not a token you should
encourage anyone to create.

**Reusing the browser session cookie.** It already works and the assistant
already forwards one. But it is `HttpOnly` by design, so a person cannot read
it to give it to an agent, and if they could, handing out a session cookie is
handing out the whole account rather than a scoped, revocable, labelled slice
of it.
