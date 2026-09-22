/**
 * Server-side access to the marketplace API.
 *
 * Every call goes through Kong, never straight to the service. The gateway owns
 * auth, rate limiting and tracing, so the frontend must not be able to skip it.
 */
import { cookies } from "next/headers";

const API_BASE =
  process.env.API_BASE_URL ?? "http://localhost:8080/api/marketplace";

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

/** The current user, or null when signed out. Never throws. */
export async function getCurrentUser(): Promise<User | null> {
  try {
    const response = await apiFetch("/auth/me");
    if (!response.ok) return null;
    return (await response.json()) as User;
  } catch {
    return null;
  }
}
