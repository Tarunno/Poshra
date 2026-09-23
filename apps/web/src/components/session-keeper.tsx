"use client";

import { useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

/**
 * Keeps a signed-in session alive.
 *
 * The access token lasts minutes and lives in an HttpOnly cookie, so the page
 * cannot read it or see when it expires. Instead of waiting for a request to
 * fail, this rotates the session before the token runs out, and again whenever
 * the tab has been in the background long enough for it to have expired.
 *
 * Refresh is a state-changing request, so it carries the double-submit CSRF
 * token from the readable cookie.
 */

// Comfortably inside the access token's lifetime (10 minutes).
const REFRESH_INTERVAL_MS = 8 * 60 * 1000;
// On regaining focus, only refresh if enough time has passed to matter.
const STALE_AFTER_MS = 4 * 60 * 1000;

function csrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)poshra_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function SessionKeeper() {
  const router = useRouter();
  // Set on mount, not during render: reading the clock while rendering makes
  // the component non-idempotent.
  const lastRefresh = useRef(0);
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    const token = csrfToken();
    if (!token) return; // signed out: nothing to keep alive

    inFlight.current = true;
    try {
      const response = await fetch("/api/marketplace/auth/refresh", {
        method: "POST",
        headers: { "X-CSRF-Token": token },
        credentials: "same-origin",
      });
      if (response.ok) {
        lastRefresh.current = Date.now();
      } else if (response.status === 401 || response.status === 403) {
        // The session is genuinely over (expired, revoked, or reuse detected).
        // Re-render so the interface stops claiming the visitor is signed in.
        router.refresh();
      }
      // Other failures (offline, 5xx, rate limited) are left for the next tick.
    } catch {
      // Network error: the next interval will try again.
    } finally {
      inFlight.current = false;
    }
  }, [router]);

  useEffect(() => {
    lastRefresh.current = Date.now();
    const timer = setInterval(refresh, REFRESH_INTERVAL_MS);

    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      // A laptop that slept for an hour comes back with an expired token and
      // no timer ticks in between.
      if (Date.now() - lastRefresh.current > STALE_AFTER_MS) refresh();
    };

    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [refresh]);

  return null;
}
