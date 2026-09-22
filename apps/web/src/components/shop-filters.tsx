import Link from "next/link";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Craft } from "@/lib/catalog";
import { cn } from "@/lib/utils";

/**
 * Filters as a plain GET form.
 *
 * Submitting navigates with query parameters, so the filters work before (and
 * without) JavaScript, every result set has a shareable URL, and the server
 * can cache those URLs. No client state to keep in sync.
 */
export function ShopFilters({
  crafts,
  active,
}: {
  crafts: Craft[];
  active: { q?: string; craft?: string; in_stock?: string };
}) {
  const chip = (
    href: string,
    label: string,
    isActive: boolean,
    bn?: string,
  ) => (
    <Link
      key={href + label}
      href={href}
      aria-current={isActive ? "page" : undefined}
      className={cn(
        "rounded-full px-4 py-1.5 text-sm font-medium transition",
        isActive
          ? "bg-foreground text-background"
          : "bg-tint-saffron hover:opacity-80",
      )}
    >
      {label}
      {bn && <span className="font-bangla ml-1.5 opacity-70">{bn}</span>}
    </Link>
  );

  const params = (extra: Record<string, string | undefined>) => {
    const next = new URLSearchParams();
    for (const [key, value] of Object.entries({ ...active, ...extra })) {
      if (value) next.set(key, value);
    }
    const qs = next.toString();
    return qs ? `/shop?${qs}` : "/shop";
  };

  return (
    <div className="space-y-5">
      <form
        action="/shop"
        method="get"
        role="search"
        className="flex flex-wrap gap-3"
      >
        <label htmlFor="q" className="sr-only">
          Search crafts
        </label>
        <div className="relative min-w-0 flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 opacity-50"
            aria-hidden
          />
          <Input
            id="q"
            name="q"
            type="search"
            defaultValue={active.q ?? ""}
            placeholder="Search jamdani, kantha, terracotta…"
            className="bg-background h-11 rounded-full border-0 pl-11"
          />
        </div>
        {/* Keep the other filters when searching. */}
        {active.craft && (
          <input type="hidden" name="craft" value={active.craft} />
        )}
        {active.in_stock && (
          <input type="hidden" name="in_stock" value={active.in_stock} />
        )}
        <Button type="submit" size="lg" className="rounded-full px-6">
          Search
        </Button>
      </form>

      <nav aria-label="Filter by craft" className="flex flex-wrap gap-2">
        {chip(params({ craft: undefined }), "All crafts", !active.craft)}
        {crafts.map((craft) =>
          chip(
            params({ craft: craft.slug }),
            craft.name,
            active.craft === craft.slug,
            craft.name_bn,
          ),
        )}
        {chip(
          params({ in_stock: active.in_stock === "true" ? undefined : "true" }),
          "Ready to ship",
          active.in_stock === "true",
        )}
      </nav>
    </div>
  );
}
