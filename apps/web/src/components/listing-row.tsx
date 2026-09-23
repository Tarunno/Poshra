import Link from "next/link";
import { TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Product } from "@/lib/catalog";
import { formatMoney } from "@/lib/format";

const statusTone: Record<Product["status"], "secondary" | "outline"> = {
  published: "secondary",
  draft: "outline",
  archived: "outline",
};

/** One of the artisan's own listings, with the numbers they act on. */
export function ListingRow({ product }: { product: Product }) {
  return (
    <li>
      <Link
        href={`/products/${product.slug}`}
        className="hover:bg-background/50 -mx-3 flex flex-wrap items-center gap-4 rounded-2xl px-3 py-4 transition"
      >
        <div className="min-w-40 flex-1">
          <p className="text-sm font-semibold">{product.title}</p>
          <p className="text-xs opacity-70">{product.craft.name}</p>
        </div>

        <Badge
          variant={statusTone[product.status]}
          className="rounded-full capitalize"
        >
          {product.status}
        </Badge>

        <p className="flex w-24 items-center justify-end gap-1 text-sm tabular-nums">
          {product.stock === 0 && (
            <TriangleAlert className="text-ink-rose size-3.5" aria-hidden />
          )}
          <span
            className={product.stock === 0 ? "text-ink-rose" : "opacity-70"}
          >
            {product.stock} left
          </span>
        </p>

        <p className="w-28 text-right text-sm font-semibold tabular-nums">
          {formatMoney(product.price_minor, product.currency)}
        </p>
      </Link>
    </li>
  );
}
