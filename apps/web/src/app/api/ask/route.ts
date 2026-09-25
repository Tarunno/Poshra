import { cookies } from "next/headers";

/**
 * The shopper's question, streamed.
 *
 * A route handler rather than a server action, because an action returns once
 * and this has to keep talking. It forwards the session and hands the
 * assistant's server-sent events through untouched — no parsing here, since
 * anything this layer understood would be a second place to change when the
 * shape of an event does.
 */
const ASSISTANT_BASE =
  process.env.ASSISTANT_BASE_URL ?? "http://localhost:8080/api/assistant";

export async function POST(request: Request) {
  const cookieHeader = (await cookies()).toString();
  const body = await request.text();

  let upstream: Response;
  try {
    upstream = await fetch(`${ASSISTANT_BASE}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(cookieHeader ? { cookie: cookieHeader } : {}),
      },
      body,
      cache: "no-store",
      // Node buffers a response body by default when it is consumed as one.
      // @ts-expect-error — undici's option, which Next passes through.
      duplex: "half",
    });
  } catch {
    return Response.json(
      { detail: "The assistant could not be reached." },
      { status: 503 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream
      .json()
      .then((body: { detail?: string }) => body.detail)
      .catch(() => undefined);
    return Response.json(
      { detail: detail ?? "The assistant is unavailable right now." },
      { status: upstream.status },
    );
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      // Nothing in front of this may hold the events back.
      "X-Accel-Buffering": "no",
    },
  });
}
