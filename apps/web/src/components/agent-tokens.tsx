"use client";

/**
 * Where a shopper connects an AI agent to Poshra.
 *
 * The screen has one job beyond the buttons: make the bargain legible. An
 * agent holding one of these can search the catalogue and fill this person's
 * basket, and cannot spend a taka — so the page says exactly that, next to the
 * thing that grants it, rather than in documentation nobody opens.
 */
import { useActionState, useState } from "react";
import { Bot, Check, Copy, KeyRound, ShieldCheck, Wallet } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  mintAgentTokenAction,
  revokeAgentTokenAction,
  type MintState,
  type RevokeState,
} from "@/lib/agent-token-actions";
import type { AgentToken } from "@/lib/agent-tokens";

function when(value: string | null) {
  if (!value) return "never";
  return new Date(value).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Copy-to-clipboard that admits it can fail: an insecure origin or a denied
 *  permission leaves the text on screen to be selected by hand. */
function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      size="sm"
      variant="secondary"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        } catch {
          setCopied(false);
        }
      }}
    >
      {copied ? (
        <Check className="size-4" aria-hidden />
      ) : (
        <Copy className="size-4" aria-hidden />
      )}
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

function TokenRow({ token }: { token: AgentToken }) {
  const [state, revoke, pending] = useActionState<RevokeState, FormData>(
    revokeAgentTokenAction,
    {},
  );

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t py-4 first:border-t-0">
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold">{token.label}</p>
        <p className="text-sm opacity-60">
          Made {when(token.created_at)} · Last used {when(token.last_used_at)} ·
          Expires {when(token.expires_at)}
        </p>
        {state.error && (
          <p className="text-destructive text-sm">{state.error}</p>
        )}
      </div>

      {token.active ? (
        <form action={revoke}>
          <input type="hidden" name="id" value={token.id} />
          <Button type="submit" size="sm" variant="ghost" disabled={pending}>
            {pending ? "Revoking…" : "Revoke"}
          </Button>
        </form>
      ) : (
        // Kept rather than deleted: somebody who worried about a token should
        // be able to see that it is dead, not just that it is gone.
        <Badge variant="secondary" className="rounded-full opacity-70">
          {token.revoked_at ? "revoked" : "expired"}
        </Badge>
      )}
    </li>
  );
}

export function AgentTokens({
  tokens,
  endpoint,
}: {
  tokens: AgentToken[];
  endpoint: string;
}) {
  const [state, mint, pending] = useActionState<MintState, FormData>(
    mintAgentTokenAction,
    {},
  );

  return (
    <div className="space-y-8">
      <section className="bg-tint-sky rounded-panel stitched p-6 sm:p-8">
        <div className="flex items-start gap-4">
          <Bot className="mt-1 size-6 shrink-0 opacity-70" aria-hidden />
          <div className="space-y-3">
            <h2 className="text-lg font-semibold">
              Let an assistant shop for you
            </h2>
            <p className="max-w-prose text-sm opacity-75">
              Poshra speaks the Model Context Protocol, so an AI assistant can
              search the catalogue, read about a piece and put things in your
              basket — on your behalf, using a token you make here and can take
              back at any time.
            </p>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="opacity-60">Server address</span>
              <code className="rounded bg-white/70 px-2 py-1 font-mono text-xs">
                {endpoint}
              </code>
              <CopyButton value={endpoint} />
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <p className="flex items-start gap-2 text-sm">
            <ShieldCheck
              className="mt-0.5 size-4 shrink-0 opacity-60"
              aria-hidden
            />
            <span>
              An assistant can browse and fill your basket, and can see nothing
              of your account beyond it.
            </span>
          </p>
          <p className="flex items-start gap-2 text-sm">
            <Wallet className="mt-0.5 size-4 shrink-0 opacity-60" aria-hidden />
            <span>
              <strong>It can never spend money.</strong> Paying happens on the
              checkout page, by you.
            </span>
          </p>
        </div>
      </section>

      <section className="rounded-panel stitched p-6 sm:p-8">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <KeyRound className="size-5 opacity-70" aria-hidden />
          Your tokens
        </h2>

        <form action={mint} className="mt-4 flex flex-wrap items-end gap-3">
          <div className="min-w-[14rem] flex-1">
            <label htmlFor="label" className="text-sm font-medium">
              What is it for?
            </label>
            <Input
              id="label"
              name="label"
              placeholder="Claude on my laptop"
              maxLength={80}
              required
              className="mt-1"
            />
          </div>
          <Button type="submit" disabled={pending}>
            {pending ? "Making…" : "Make a token"}
          </Button>
        </form>
        {state.error && (
          <p className="text-destructive mt-2 text-sm">{state.error}</p>
        )}

        {state.token && (
          <div className="bg-tint-saffron mt-6 rounded-lg p-4">
            <p className="text-sm font-semibold">
              Copy {state.label} now — this is the only time it is shown.
            </p>
            <p className="mt-1 text-sm opacity-70">
              Nothing here keeps it. If you lose it, make another one.
            </p>
            <div className="mt-3 flex items-center gap-2">
              <code className="min-w-0 flex-1 overflow-x-auto rounded bg-white/70 px-3 py-2 font-mono text-xs break-all">
                {state.token}
              </code>
              <CopyButton value={state.token} />
            </div>
          </div>
        )}

        {tokens.length > 0 ? (
          <ul className="mt-6">
            {tokens.map((token) => (
              <TokenRow key={token.id} token={token} />
            ))}
          </ul>
        ) : (
          <p className="mt-6 text-sm opacity-60">
            No tokens yet. Make one above to connect an assistant.
          </p>
        )}
      </section>
    </div>
  );
}
