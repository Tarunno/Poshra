"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowUp, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ProductCard } from "@/components/product-card";
import { askAssistant, type ChatTurn } from "@/lib/assistant-actions";
import type { Product } from "@/lib/catalog";

type Entry = ChatTurn & { products?: Product[]; checkoutReady?: boolean };

const OPENERS = [
  "A wedding gift under ৳8,000",
  "Something handwoven from Sylhet",
  "A nakshi kantha with lotus motifs",
];

/**
 * The shopping conversation.
 *
 * State lives here rather than on the server: the assistant is stateless, so
 * the whole history is sent with each question and nothing about what someone
 * asked is kept once they close the tab.
 */
export function ShoppingChat({ compact = false }: { compact?: boolean }) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string>();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries, pending]);

  async function send(question: string) {
    const text = question.trim();
    if (!text || pending) return;

    const history: Entry[] = [...entries, { role: "user", content: text }];
    setEntries(history);
    setDraft("");
    setError(undefined);
    setPending(true);

    // Only the roles and text go back — the products attached to earlier
    // answers are for display, and resending them would pay to re-read them.
    const answer = await askAssistant(
      history.map(({ role, content }) => ({ role, content })),
    );
    setPending(false);

    if (answer.error) {
      setError(answer.error);
      return;
    }
    setEntries([
      ...history,
      {
        role: "assistant",
        content: answer.reply,
        products: answer.products,
        checkoutReady: answer.checkoutReady,
      },
    ]);
  }

  return (
    <div className={compact ? "flex h-full flex-col" : "space-y-5"}>
      <div
        className={
          // In the panel this is the only thing that scrolls, which is what
          // keeps the composer pinned to the bottom instead of drifting up
          // behind the conversation.
          compact
            ? "min-h-0 flex-1 space-y-5 overflow-y-auto pr-1"
            : "space-y-5"
        }
      >
        {entries.length === 0 && (
          <div
            className={
              compact
                ? "bg-tint-sky rounded-2xl p-5"
                : "bg-tint-sky rounded-panel stitched p-7 sm:p-9"
            }
          >
            <p className="bg-background/70 text-ink-sky inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold tracking-wide uppercase">
              <Sparkles className="size-3.5" aria-hidden />
              Ask for what you want
            </p>
            <h2
              className={`mt-4 max-w-lg leading-snug font-bold tracking-tight text-balance ${
                compact ? "text-base" : "text-2xl"
              }`}
            >
              Describe the piece you are looking for, the way you would to a
              shopkeeper.
            </h2>
            <div className="mt-6 flex flex-wrap gap-2">
              {OPENERS.map((opener) => (
                <Button
                  key={opener}
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="bg-background/70 rounded-full"
                  onClick={() => send(opener)}
                >
                  {opener}
                </Button>
              ))}
            </div>
          </div>
        )}

        {entries.map((entry, index) => (
          <div key={index}>
            {entry.role === "user" ? (
              <p className="bg-tint-lilac ml-auto max-w-lg rounded-3xl px-5 py-3 text-sm font-medium">
                {entry.content}
              </p>
            ) : (
              <div className="space-y-5">
                <p className="max-w-2xl text-[0.95rem] leading-relaxed whitespace-pre-wrap">
                  {entry.content}
                </p>
                {entry.checkoutReady && (
                  // The assistant totals a cart; paying happens on the checkout
                  // page, where the order is reviewed and the idempotency key is
                  // minted. The model has no way to take money.
                  <Button asChild size="lg" className="rounded-full px-7">
                    <Link href="/checkout">Review and pay</Link>
                  </Button>
                )}
                {entry.products && entry.products.length > 0 && (
                  <div
                    className={
                      compact
                        ? "grid grid-cols-1 gap-4"
                        : "grid grid-cols-2 gap-5 lg:grid-cols-3"
                    }
                  >
                    {entry.products.map((product) => (
                      <ProductCard key={product.id} product={product} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {pending && (
          <p aria-live="polite" className="text-sm opacity-60">
            Looking through the workshops…
          </p>
        )}

        {error && (
          <p
            role="alert"
            className="text-ink-rose flex items-center gap-1.5 text-sm font-medium"
          >
            <AlertCircle className="size-4" aria-hidden />
            {error}
          </p>
        )}

        <div ref={endRef} />
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          send(draft);
        }}
        className={`bg-background flex items-center gap-2 rounded-full p-2 ${
          compact ? "mt-3 shrink-0 border" : "sticky bottom-4 shadow-sm"
        }`}
      >
        <label htmlFor="question" className="sr-only">
          What are you looking for?
        </label>
        <Input
          id="question"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          maxLength={2000}
          placeholder="A handmade gift under ৳5,000…"
          className="h-11 flex-1 border-0 bg-transparent px-4 shadow-none focus-visible:ring-0"
          disabled={pending}
        />
        <Button
          type="submit"
          size="icon"
          className="size-10 shrink-0 rounded-full"
          disabled={pending || draft.trim().length === 0}
          aria-label="Ask"
        >
          <ArrowUp className="size-4" aria-hidden />
        </Button>
      </form>
    </div>
  );
}
