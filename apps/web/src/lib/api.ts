/**
 * Server-side access to the marketplace API.
 *
 * Every call goes through Kong, never straight to the service. The gateway owns
 * auth, rate limiting and tracing, so the frontend must not be able to skip it.
 */
import { cache } from "react";
import { cookies } from "next/headers";

const API_BASE =
  process.env.API_BASE_URL ?? "http://localhost:8080/api/marketplace";

/**
 * Writes take the public route instead of the internal one.
 *
 * The internal route is unlimited on purpose: one page render makes several
 * reads and every pod shares a source address, so a per-client limit would
 * throttle the storefront itself. Writes have no such problem — one user
 * action is one write — and a Server Action is a public POST endpoint, so
 * sending writes down the unlimited path would hand an attacker an
 * unthrottled way in. The public route is rate limited per user.
 */
const WRITE_BASE = process.env.API_WRITE_BASE_URL ?? API_BASE;

export type User = {
  id: string;
  email: string;
  full_name: string;
  role: "buyer" | "artisan" | "admin";
};

/** Forwards the browser's session cookies so the API sees the logged-in user. */
export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const cookieHeader = (await cookies()).toString();
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      ...(cookieHeader ? { cookie: cookieHeader } : {}),
    },
    // Session-dependent data must never be served from a cache.
    cache: "no-store",
  });
}

/** Like apiFetch, but through the rate-limited route. See WRITE_BASE. */
export async function apiWriteFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const cookieHeader = (await cookies()).toString();
  return fetch(`${WRITE_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      ...(cookieHeader ? { cookie: cookieHeader } : {}),
    },
    cache: "no-store",
  });
}

/**
 * The current user, or null when signed out. Never throws.
 *
 * Cached for the duration of one render: the layout and the page below it both
 * ask who the visitor is, and the gateway should only be told once.
 */
export const getCurrentUser = cache(async (): Promise<User | null> => {
  try {
    const response = await apiFetch("/users/me");
    if (!response.ok) return null;
    return (await response.json()) as User;
  } catch {
    return null;
  }
});
