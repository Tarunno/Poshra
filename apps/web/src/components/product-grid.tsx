import { ProductCard } from "@/components/product-card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Product } from "@/lib/catalog";

export function ProductGrid({
  products,
  saved,
  actions = false,
}: {
  products: Product[];
  /** The slugs this shopper saved, fetched once for the page. */
  saved?: Set<string>;
  actions?: boolean;
}) {
  return (
    <div className="grid grid-cols-2 gap-x-5 gap-y-9 lg:grid-cols-3">
      {products.map((product) => (
        <ProductCard
          key={product.id}
          product={product}
          actions={actions}
          saved={saved?.has(product.slug) ?? false}
        />
      ))}
    </div>
  );
}

/** Shown while the grid streams in, matching its shape so nothing jumps. */
export function ProductGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div
      className="grid grid-cols-2 gap-x-5 gap-y-9 lg:grid-cols-3"
      aria-hidden
    >
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="space-y-3">
          <Skeleton className="aspect-[4/5] rounded-3xl" />
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="h-3 w-2/5" />
        </div>
      ))}
    </div>
  );
}
