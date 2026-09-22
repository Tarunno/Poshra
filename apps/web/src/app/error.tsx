"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

/**
 * Error boundary for the app.
 *
 * The message is deliberately vague: internal failures must not leak service
 * names or stack traces to visitors. The details go to the server log, and
 * later to the trace, through the digest.
 */
export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("page error", {
      digest: error.digest,
      message: error.message,
    });
  }, [error]);

  return (
    <div className="bg-tint-saffron rounded-panel stitched mx-auto max-w-xl p-10 text-center">
      <h1 className="text-3xl font-extrabold tracking-tight">
        Something came loose.
      </h1>
      <p className="mt-3 text-sm opacity-75">
        We could not load this page. It is usually temporary — try again in a
        moment.
      </p>
      {error.digest && (
        <p className="mt-2 text-xs opacity-50">
          Reference: <code>{error.digest}</code>
        </p>
      )}
      <Button onClick={reset} className="mt-7 rounded-full px-6">
        Try again
      </Button>
    </div>
  );
}
