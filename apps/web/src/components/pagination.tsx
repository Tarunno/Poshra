import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/** Offset pagination that keeps the current filters in the URL. */
export function Pagination({
  count,
  limit,
  offset,
  searchParams,
}: {
  count: number;
  limit: number;
  offset: number;
  searchParams: Record<string, string | undefined>;
}) {
  const pages = Math.ceil(count / limit);
  if (pages <= 1) return null;

  const current = Math.floor(offset / limit) + 1;
  const href = (page: number) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(searchParams)) {
      if (value && key !== "offset") params.set(key, value);
    }
    if (page > 1) params.set("offset", String((page - 1) * limit));
    const qs = params.toString();
    return qs ? `/shop?${qs}` : "/shop";
  };

  const style = "rounded-full px-4 py-2 text-sm font-medium";

  return (
    <nav
      aria-label="Pagination"
      className="flex items-center justify-center gap-2 pt-4"
    >
      {current > 1 ? (
        <Link
          href={href(current - 1)}
          rel="prev"
          className={cn(style, "bg-tint-saffron")}
        >
          <ChevronLeft className="inline size-4" aria-hidden /> Previous
        </Link>
      ) : (
        <span className={cn(style, "opacity-40")} aria-hidden>
          <ChevronLeft className="inline size-4" /> Previous
        </span>
      )}

      <span className="px-3 text-sm opacity-70">
        Page {current} of {pages}
      </span>

      {current < pages ? (
        <Link
          href={href(current + 1)}
          rel="next"
          className={cn(style, "bg-tint-saffron")}
        >
          Next <ChevronRight className="inline size-4" aria-hidden />
        </Link>
      ) : (
        <span className={cn(style, "opacity-40")} aria-hidden>
          Next <ChevronRight className="inline size-4" />
        </span>
      )}
    </nav>
  );
}
