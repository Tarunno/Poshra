/**
 * Reading the assistant's answer as it is written.
 *
 * Runs in the browser, so it is here rather than in a server action: the
 * whole point is that the words arrive before the answer does, and a server
 * action can only hand back a finished thing.
 */
import type { Product } from "./catalog";

export type Answer = {
  reply: string;
  products: Product[];
  tool_calls: number;
  checkout_ready: boolean;
};

export type StreamHandlers = {
  onDelta: (text: string) => void;
  onStatus: (text: string) => void;
};

export async function askStreaming(
  messages: { role: "user" | "assistant"; content: string }[],
  handlers: StreamHandlers,
): Promise<{ answer?: Answer; error?: string }> {
  let response: Response;
  try {
    response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });
  } catch {
    return { error: "The assistant could not be reached." };
  }

  if (!response.ok || !response.body) {
    const detail = await response
      .json()
      .then((body: { detail?: string }) => body.detail)
      .catch(() => undefined);
    if (response.status === 401)
      return { error: "Sign in to ask the assistant." };
    return { error: detail ?? "The assistant is unavailable right now." };
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  // Events arrive split across chunks as often as not, so what is left after
  // the last blank line is kept rather than parsed.
  let pending = "";
  let answer: Answer | undefined;
  let error: string | undefined;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    pending += decoder.decode(value, { stream: true });

    const events = pending.split("\n\n");
    pending = events.pop() ?? "";

    for (const block of events) {
      const line = block.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        const event = JSON.parse(line.slice(6));
        if (event.type === "delta") handlers.onDelta(event.text);
        else if (event.type === "status") handlers.onStatus(event.text);
        else if (event.type === "answer") answer = event as Answer;
        else if (event.type === "error") error = event.detail;
      } catch {
        // A half-written event is not an error; the rest of it is coming.
      }
    }
  }

  return { answer, error };
}
