import { Suspense } from "react";
import Link from "next/link";
import type { Metadata } from "next";
import { PackageSearch, Search } from "lucide-react";
import { Pagination } from "@/components/pagination";
import { savedSlugs } from "@/lib/favourite-actions";
import { ProductGrid, ProductGridSkeleton } from "@/components/product-grid";
import { ShopSidebar, type ActiveFilters } from "@/components/shop-sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getFacets, listProducts, type ProductQuery } from "@/lib/catalog";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 12;

const SORTS = [
  { value: "newest", label: "Newest" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
] as const;

export const metadata: Metadata = {
  title: "Shop handmade crafts — Poshra",
  description:
    "Jamdani, nakshi kantha, terracotta, jute and bell metal, bought directly from the artisans who make them in Bangladesh.",
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/** Query parameters are user input: take only what we know, as strings. */
function readQuery(raw: Record<string, string | string[] | undefined>) {
  const single = (key: string) => {
    const value = raw[key];
    return typeof value === "string" && value.length > 0 ? value : undefined;
  };
  const offset = Number.parseInt(single("offset") ?? "0", 10);
  const sort = single("sort");
  return {
    q: single("q"),
    craft: single("craft"),
    division: single("division"),
    min_price: single("min_price"),
    max_price: single("max_price"),
    in_stock: single("in_stock") === "true" ? "true" : undefined,
    sort: SORTS.some((option) => option.value === sort) ? sort : undefined,
    offset: Number.isFinite(offset) && offset > 0 ? offset : 0,
  };
}

function sortHref(active: ActiveFilters, sort: string): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries({ ...active, sort })) {
    if (value) params.set(key, value);
  }
  return `/shop?${params.toString()}`;
}

async function Results({
  query,
}: {
  query: ProductQuery & { offset: number };
}) {
  // Two requests, on purpose. The catalogue is shared and cached; what this
  // shopper saved is theirs alone and never cached. Folding the second into
  // the first would poison the cache with one person's hearts.
  const [page, saved] = await Promise.all([
    listProducts({ ...query, limit: PAGE_SIZE }),
    savedSlugs(),
  ]);

  if (page.count === 0) {
    return (
      <div className="bg-tint-sky rounded-panel stitched px-6 py-16 text-center">
        <PackageSearch className="mx-auto size-8 opacity-60" aria-hidden />
        <p className="mt-4 text-lg font-semibold">Nothing matches that yet.</p>
        <p className="mx-auto mt-2 max-w-sm text-sm opacity-70">
          Poshra is young and the catalog is still growing. Try a wider price
          range, or clear the filters.
        </p>
        <Button asChild variant="outline" className="mt-6 rounded-full">
          <Link href="/shop">Clear filters</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <ProductGrid products={page.results} saved={saved} actions />
      <Pagination
        count={page.count}
        limit={PAGE_SIZE}
        offset={query.offset}
        searchParams={{
          q: query.q,
          craft: query.craft,
          division: query.division,
          min_price: query.min_price,
          max_price: query.max_price,
          in_stock: query.in_stock,
          sort: query.sort,
        }}
      />
    </div>
  );
}

export default async function ShopPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const { offset, ...active } = readQuery(await searchParams);
  const query = { ...active, offset };
  // Facets are needed to render the sidebar, so they are awaited; the product
  // grid streams in behind a skeleton.
  const facets = await getFacets(active);
  const selectedCraft = facets.crafts.find(
    (craft) => craft.slug === query.craft,
  );

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          {selectedCraft ? selectedCraft.name : "Every piece, made by hand."}
          {selectedCraft && (
            <span className="font-bangla ml-2 text-xl opacity-50">
              {selectedCraft.name_bn}
            </span>
          )}
        </h1>
        <p className="max-w-2xl text-pretty opacity-70">
          Bought directly from the maker, with the district it came from
          attached to every piece.
        </p>
      </header>

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
            defaultValue={query.q ?? ""}
            placeholder="Search jamdani, kantha, terracotta…"
            className="bg-background h-11 rounded-full border-0 pl-11"
          />
        </div>
        {/* Searching keeps the filters the visitor already chose. */}
        {Object.entries(active).map(([key, value]) =>
          value && key !== "q" ? (
            <input key={key} type="hidden" name={key} value={value} />
          ) : null,
        )}
        <Button type="submit" size="lg" className="rounded-full px-6">
          Search
        </Button>
      </form>

      <div className="grid gap-8 lg:grid-cols-[17rem_1fr]">
        <ShopSidebar facets={facets} active={active} />

        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm opacity-70" role="status" aria-live="polite">
              {facets.total} {facets.total === 1 ? "piece" : "pieces"}
              {query.q && <> for “{query.q}”</>}
            </p>

            {!query.q && (
              <nav aria-label="Sort" className="flex flex-wrap gap-1.5">
                {SORTS.map((option) => {
                  const isActive = (query.sort ?? "newest") === option.value;
                  return (
                    <Link
                      key={option.value}
                      href={sortHref(active, option.value)}
                      aria-current={isActive ? "true" : undefined}
                      className={cn(
                        "rounded-full px-3 py-1.5 text-xs font-medium transition",
                        isActive
                          ? "bg-foreground text-background"
                          : "bg-tint-mint hover:opacity-80",
                      )}
                    >
                      {option.label}
                    </Link>
                  );
                })}
              </nav>
            )}
          </div>

          <Suspense
            key={JSON.stringify(query)}
            fallback={<ProductGridSkeleton />}
          >
            <Results query={query} />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
