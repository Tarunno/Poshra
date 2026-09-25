"use server";

/**
 * Asking Pahara why the cluster did something.
 *
 * Through the public gateway route, like every other write: that is where the
 * session is verified, where the role is read from the signed token, and where
 * the rate limiter sits. The role is checked again by the service itself —
 * this page not rendering is a courtesy, not a control.
 */
import { cookies } from "next/headers";

const PAHARA_BASE =
  process.env.PAHARA_BASE_URL ?? "http://localhost:8080/api/pahara";

/** One query it ran, in the order it ran them. */
export type Look = {
  tool: string;
  /** Why it looked, in its own words. The query is the evidence; this is the
   *  sentence somebody reading at speed actually needs. */
  why?: string;
  query?: string;
  trace_id?: string;
  since?: string;
};

export type Explanation = {
  answer: string;
  looked_at: Look[];
  looks: number;
  error?: string;
};

export async function askPahara(
  _previous: Explanation,
  formData: FormData,
): Promise<Explanation> {
  const question = String(formData.get("question") ?? "").trim();
  if (question.length < 3) {
    return {
      answer: "",
      looked_at: [],
      looks: 0,
      error: "Ask a question first.",
    };
  }

  const empty = { answer: "", looked_at: [], looks: 0 };
  const cookieHeader = (await cookies()).toString();

  try {
    const response = await fetch(`${PAHARA_BASE}/explain`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(cookieHeader ? { cookie: cookieHeader } : {}),
      },
      body: JSON.stringify({ question }),
      cache: "no-store",
    });

    if (response.ok) return (await response.json()) as Explanation;

    const body = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    if (response.status === 401) return { ...empty, error: "Sign in again." };
    if (response.status === 403) {
      return { ...empty, error: body.detail ?? "That needs an admin." };
    }
    if (response.status === 429) {
      // Deliberately tight: an operator asking repeatedly during an incident
      // is when a runaway bill is easiest to miss.
      return { ...empty, error: "One question a minute. Try again shortly." };
    }
    return {
      ...empty,
      error: body.detail ?? "Pahara is unavailable right now.",
    };
  } catch {
    return { ...empty, error: "Pahara could not be reached." };
  }
}
