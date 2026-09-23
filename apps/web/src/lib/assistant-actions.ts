"use server";

/**
 * Asking the shopping assistant.
 *
 * The conversation lives in the browser and is sent whole each time: the
 * service is stateless, so a refresh starts a new conversation and nothing
 * about what someone asked is kept server-side.
 *
 * Like the other writes, this goes through the public gateway route rather
 * than the internal one — every answer is a paid model call, and that route is
 * the one with a rate limiter on it.
 */
import { cookies } from "next/headers";

import type { Product } from "./catalog";

const ASSISTANT_BASE =
  process.env.ASSISTANT_BASE_URL ?? "http://localhost:8080/api/assistant";

export type ChatTurn = { role: "user" | "assistant"; content: string };

export type ChatAnswer = {
  reply: string;
  products: Product[];
  error?: string;
};

const MAX_TURNS = 20;
const MAX_CHARS = 2000;

export async function askAssistant(history: ChatTurn[]): Promise<ChatAnswer> {
  const messages = history
    .slice(-MAX_TURNS)
    .map((turn) => ({
      role: turn.role,
      content: turn.content.slice(0, MAX_CHARS),
    }))
    .filter((turn) => turn.content.trim().length > 0);

  if (messages.length === 0 || messages[messages.length - 1].role !== "user") {
    return { reply: "", products: [], error: "Ask a question first." };
  }

  const cookieHeader = (await cookies()).toString();

  try {
    const response = await fetch(`${ASSISTANT_BASE}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(cookieHeader ? { cookie: cookieHeader } : {}),
      },
      body: JSON.stringify({ messages }),
      cache: "no-store",
    });

    if (response.status === 401) {
      return {
        reply: "",
        products: [],
        error: "Sign in to ask the assistant.",
      };
    }
    if (response.status === 429) {
      // Either the gateway's own limit or the model being out of quota; both
      // mean wait, and neither means the assistant is broken.
      const body = (await response.json().catch(() => ({}))) as {
        detail?: string;
      };
      return {
        reply: "",
        products: [],
        error: body.detail ?? "One question at a time — try again in a moment.",
      };
    }
    if (!response.ok) {
      return {
        reply: "",
        products: [],
        error: "The assistant is unavailable right now.",
      };
    }

    const body = (await response.json()) as {
      reply: string;
      products: Product[];
    };
    return { reply: body.reply, products: body.products ?? [] };
  } catch {
    return {
      reply: "",
      products: [],
      error: "The assistant could not be reached.",
    };
  }
}
