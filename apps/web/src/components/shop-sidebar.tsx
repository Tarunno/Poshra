import Link from "next/link";
import { SlidersHorizontal, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { KanthaRule } from "@/components/motifs";
import type { Facets } from "@/lib/catalog";
import { formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

export type ActiveFilters = {
  q?: string;
  craft?: string;
  division?: string;
  min_price?: string;
  max_price?: string;
  in_stock?: string;
  sort?: string;
};

const DIVISION_LABELS: Record<string, string> = {
  barishal: "Barishal",
  chattogram: "Chattogram",
  dhaka: "Dhaka",
  khulna: "Khulna",
  mymensingh: "Mymensingh",
  rajshahi: "Rajshahi",
  rangpur: "Rangpur",
  sylhet: "Sylhet",
};

/** Build a /shop URL with one filter changed and the rest kept. */
function hrefWith(
  active: ActiveFilters,
  changes: Partial<ActiveFilters>,
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries({ ...active, ...changes })) {
    if (value) params.set(key, value);
  }
  const qs = params.toString();
  return qs ? `/shop?${qs}` : "/shop";
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h3 className="text-xs font-semibold tracking-wide uppercase opacity-60">
        {title}
      </h3>
      {children}
    </section>
  );
}

function FilterLink({
  href,
  label,
  bn,
  count,
  isActive,
}: {
  href: string;
  label: string;
  bn?: string;
  count?: number;
  isActive: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={isActive ? "true" : undefined}
      className={cn(
        "flex items-center justify-between gap-2 rounded-xl px-3 py-2 text-sm transition",
        isActive
          ? "bg-foreground text-background font-semibold"
          : "hover:bg-background/70",
      )}
    >
      <span className="truncate">
        {label}
        {bn && (
          <span className="font-bangla ml-1.5 text-xs opacity-60">{bn}</span>
        )}
      </span>
      {count !== undefined && (
        <span
          className={cn(
            "text-xs tabular-nums",
            isActive ? "opacity-80" : "opacity-50",
          )}
        >
          {count}
        </span>
      )}
    </Link>
  );
}

function Filters({
  facets,
  active,
}: {
  facets: Facets;
  active: ActiveFilters;
}) {
  const hasFilters = Boolean(
    active.craft ||
    active.division ||
    active.min_price ||
    active.max_price ||
    active.in_stock,
  );

  return (
    <div className="space-y-7">
      <Section title="Craft">
        <div className="space-y-0.5">
          <FilterLink
            href={hrefWith(active, { craft: undefined })}
            label="All crafts"
            count={facets.crafts.reduce((sum, craft) => sum + craft.count, 0)}
            isActive={!active.craft}
          />
          {facets.crafts.map((craft) => (
            <FilterLink
              key={craft.slug}
              href={hrefWith(active, { craft: craft.slug })}
              label={craft.name}
              bn={craft.name_bn}
              count={craft.count}
              isActive={active.craft === craft.slug}
            />
          ))}
        </div>
      </Section>

      {facets.divisions.length > 1 && (
        <Section title="Where it was made">
          <div className="space-y-0.5">
            <FilterLink
              href={hrefWith(active, { division: undefined })}
              label="Anywhere"
              isActive={!active.division}
            />
            {facets.divisions.map((division) => (
              <FilterLink
                key={division.value}
                href={hrefWith(active, { division: division.value })}
                label={DIVISION_LABELS[division.value] ?? division.value}
                count={division.count}
                isActive={active.division === division.value}
              />
            ))}
          </div>
        </Section>
      )}

      <Section title="Price">
        {/* A GET form, so the range works without JavaScript and the result has
            a shareable URL. Values are in taka; the API takes minor units. */}
        <form action="/shop" method="get" className="space-y-3">
          {Object.entries(active).map(([key, value]) =>
            value && key !== "min_price" && key !== "max_price" ? (
              <input key={key} type="hidden" name={key} value={value} />
            ) : null,
          )}
          <div className="flex items-center gap-2">
            <label htmlFor="min_price" className="sr-only">
              Minimum price in taka
            </label>
            <Input
              id="min_price"
              name="min_price"
              type="number"
              min={0}
              inputMode="numeric"
              placeholder="Min"
              defaultValue={active.min_price ?? ""}
              className="bg-background h-10 rounded-xl border-0"
            />
            <span aria-hidden className="opacity-50">
              –
            </span>
            <label htmlFor="max_price" className="sr-only">
              Maximum price in taka
            </label>
            <Input
              id="max_price"
              name="max_price"
              type="number"
              min={0}
              inputMode="numeric"
              placeholder="Max"
              defaultValue={active.max_price ?? ""}
              className="bg-background h-10 rounded-xl border-0"
            />
          </div>
          <p className="text-xs opacity-60">
            {facets.total > 0
              ? `${formatMoney(facets.price.min, "BDT")} – ${formatMoney(facets.price.max, "BDT")} in this selection`
              : "No pieces in this selection"}
          </p>
          <Button
            type="submit"
            variant="outline"
            size="sm"
            className="w-full rounded-full"
          >
            Apply price
          </Button>
        </form>
      </Section>

      <Section title="Availability">
        <FilterLink
          href={hrefWith(active, {
            in_stock: active.in_stock === "true" ? undefined : "true",
          })}
          label="Ready to ship"
          count={facets.in_stock}
          isActive={active.in_stock === "true"}
        />
      </Section>

      {hasFilters && (
        <>
          <KanthaRule className="h-3 w-full opacity-40" />
          <Link
            href={
              active.q ? `/shop?q=${encodeURIComponent(active.q)}` : "/shop"
            }
            className="inline-flex items-center gap-1.5 text-sm font-semibold underline underline-offset-4"
          >
            <X className="size-3.5" aria-hidden /> Clear filters
          </Link>
        </>
      )}
    </div>
  );
}

/**
 * Filter sidebar.
 *
 * Every control is a link or a GET form, so filtering works without
 * JavaScript, each result set has its own URL, and the server can cache it.
 * On small screens the whole panel collapses into a native disclosure, which
 * needs no client code either.
 */
export function ShopSidebar({
  facets,
  active,
}: {
  facets: Facets;
  active: ActiveFilters;
}) {
  return (
    <aside aria-label="Filters">
      <details className="bg-tint-saffron rounded-panel stitched group p-5 lg:hidden">
        <summary className="flex cursor-pointer items-center gap-2 font-semibold">
          <SlidersHorizontal className="size-4" aria-hidden />
          Filters
          <span className="ml-auto text-sm opacity-60">
            {facets.total} pieces
          </span>
        </summary>
        <div className="mt-5">
          <Filters facets={facets} active={active} />
        </div>
      </details>

      <div className="bg-tint-saffron rounded-panel stitched hidden p-6 lg:sticky lg:top-24 lg:block">
        <Filters facets={facets} active={active} />
      </div>
    </aside>
  );
}
