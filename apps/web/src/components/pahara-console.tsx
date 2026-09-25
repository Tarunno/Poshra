"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { AlertCircle, Search, Telescope } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ChatAnswer } from "@/components/chat-answer";
import { askPahara, type Explanation, type Look } from "@/lib/pahara-actions";

const OPENERS = [
  "What was the slowest request in the last hour, and where did the time go?",
  "Has anything errored today?",
  "Why does the assistant take so long to answer?",
];

/** Where a query can be opened for yourself. The point of the trail is that it
 *  is followable; a citation nobody can check is decoration. */
function evidence(look: Look, grafana: string): string | undefined {
  if (look.trace_id) {
    return `${grafana}/explore?left=${encodeURIComponent(
      JSON.stringify({
        datasource: "tempo",
        queries: [{ refId: "A", query: look.trace_id, queryType: "traceql" }],
        range: { from: "now-3h", to: "now" },
      }),
    )}`;
  }
  return undefined;
}

function AskButton() {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      size="lg"
      className="rounded-full px-7"
      disabled={pending}
    >
      <Search className="size-4" aria-hidden />
      {pending ? "Looking…" : "Ask Pahara"}
    </Button>
  );
}

/**
 * পাহারা — the watch.
 *
 * The answer is only half of it. Underneath is every query it ran, in order,
 * so a claim can be followed back to the thing it came from: a trace id opens
 * in Grafana, a LogQL query is there to be pasted. An explanation that cites
 * nothing looks like exactly that.
 */
export function PaharaConsole({ grafanaUrl }: { grafanaUrl: string }) {
  const [state, formAction] = useActionState(askPahara, {} as Explanation);

  return (
    <div className="space-y-6">
      <form action={formAction} className="space-y-3">
        <label htmlFor="question" className="text-sm font-semibold">
          What would you like to know about the cluster?
        </label>
        <textarea
          id="question"
          name="question"
          rows={3}
          maxLength={1000}
          className="bg-background w-full rounded-xl border-0 p-4"
          placeholder="Why was checkout slow in the last hour?"
        />
        <div className="flex flex-wrap items-center gap-3">
          <AskButton />
          <p className="text-xs opacity-60">
            Read-only. Pahara can say what happened; it cannot change anything.
          </p>
        </div>
      </form>

      {!state.answer && !state.error && (
        <div className="flex flex-wrap gap-2">
          {OPENERS.map((opener) => (
            <form key={opener} action={formAction}>
              <input type="hidden" name="question" value={opener} />
              <Button
                type="submit"
                variant="ghost"
                size="sm"
                className="bg-background/70 rounded-full text-left"
              >
                {opener}
              </Button>
            </form>
          ))}
        </div>
      )}

      {state.error && (
        <Alert variant="destructive" className="rounded-2xl">
          <AlertCircle className="size-4" />
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}

      {state.answer && (
        <div className="space-y-5">
          <ChatAnswer>{state.answer}</ChatAnswer>

          <div className="bg-background/70 rounded-2xl p-4">
            <p className="flex items-center gap-1.5 text-xs font-semibold tracking-wide uppercase opacity-60">
              <Telescope className="size-3.5" aria-hidden />
              {state.looks === 0
                ? "It answered without looking at anything"
                : `What it looked at · ${state.looks}`}
            </p>
            {state.looked_at.length > 0 && (
              <ol className="mt-3 space-y-3 text-sm">
                {state.looked_at.map((look, index) => {
                  const href = evidence(look, grafanaUrl);
                  const detail = look.trace_id ?? look.query ?? "";
                  return (
                    <li key={index} className="space-y-1">
                      {/* What it was checking, in words. The query underneath
                          is the evidence; this is what somebody reading at
                          speed needs, and PromQL is not an explanation. */}
                      <p className="flex flex-wrap items-baseline gap-2">
                        <span aria-hidden className="opacity-40">
                          {index + 1}.
                        </span>
                        <span>{look.why ?? look.tool.replace(/_/g, " ")}</span>
                        {look.since && (
                          <span className="text-xs opacity-50">
                            · over {look.since}
                          </span>
                        )}
                      </p>
                      {detail &&
                        (href ? (
                          <a
                            href={href}
                            target="_blank"
                            rel="noreferrer"
                            className="ml-5 block font-mono text-xs break-all underline underline-offset-4 opacity-60"
                          >
                            {detail}
                          </a>
                        ) : (
                          <code className="bg-muted ml-5 block rounded px-1.5 py-1 font-mono text-xs break-all opacity-70">
                            {detail}
                          </code>
                        ))}
                    </li>
                  );
                })}
              </ol>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
