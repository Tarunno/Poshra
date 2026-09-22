import { Suspense } from "react";
import type { Metadata } from "next";
import { PackageSearch } from "lucide-react";
import { Pagination } from "@/components/pagination";
import { ProductGrid, ProductGridSkeleton } from "@/components/product-grid";
import { ShopFilters } from "@/components/shop-filters";
import { listCrafts, listProducts, type ProductQuery } from "@/lib/catalog";

const PAGE_SIZE = 12;

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
  return {
    q: single("q"),
    craft: single("craft"),
    division: single("division"),
    min_price: single("min_price"),
    max_price: single("max_price"),
    in_stock: single("in_stock") === "true" ? "true" : undefined,
    offset: Number.isFinite(offset) && offset > 0 ? offset : 0,
  };
}

async function Results({
  query,
}: {
  query: ProductQuery & { offset: number };
}) {
  const page = await listProducts({ ...query, limit: PAGE_SIZE });

  if (page.count === 0) {
    return (
      <div className="bg-tint-sky rounded-panel stitched px-6 py-16 text-center">
        <PackageSearch className="mx-auto size-8 opacity-60" aria-hidden />
        <p className="mt-4 text-lg font-semibold">Nothing matches that yet.</p>
        <p className="mx-auto mt-2 max-w-sm text-sm opacity-70">
          Poshra is young and the catalog is still growing. Try a broader
          search, or browse all crafts.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {/* Announced to screen readers when the result set changes. */}
      <p className="text-sm opacity-70" role="status" aria-live="polite">
        {page.count} {page.count === 1 ? "piece" : "pieces"}
      </p>
      <ProductGrid products={page.results} />
      <Pagination
        count={page.count}
        limit={PAGE_SIZE}
        offset={query.offset}
        searchParams={{
          q: query.q,
          craft: query.craft,
          in_stock: query.in_stock,
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
  const query = readQuery(await searchParams);
  // Crafts are needed to render the filters, so they are awaited here; the
  // product grid streams in behind a skeleton.
  const crafts = await listCrafts();

  return (
    <div className="space-y-9">
      <header className="space-y-3">
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          {query.craft
            ? (crafts.find((c) => c.slug === query.craft)?.name ?? "Crafts")
            : "Every piece, made by hand."}
        </h1>
        <p className="max-w-2xl text-pretty opacity-70">
          {query.craft
            ? (crafts.find((c) => c.slug === query.craft)?.summary ?? "")
            : "Bought directly from the maker, with the district it came from attached to every piece."}
        </p>
      </header>

      <ShopFilters crafts={crafts} active={query} />

      <Suspense key={JSON.stringify(query)} fallback={<ProductGridSkeleton />}>
        <Results query={query} />
      </Suspense>
    </div>
  );
}
