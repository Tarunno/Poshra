import Link from "next/link";
import { CraftTile } from "@/components/craft-tile";
import { Badge } from "@/components/ui/badge";
import type { Product } from "@/lib/catalog";
import { formatMoney } from "@/lib/format";

export function ProductCard({ product }: { product: Product }) {
  const image = product.images[0];

  return (
    <article className="group">
      <Link
        href={`/products/${product.slug}`}
        className="focus-visible:ring-foreground/50 block rounded-3xl focus-visible:ring-2 focus-visible:ring-offset-4 focus-visible:outline-none"
      >
        <div className="rounded-3xl relative aspect-[4/5] overflow-hidden">
          {image ? (
            // eslint-disable-next-line @next/next/no-img-element -- artisan-supplied URLs are not on a configured loader yet
            <img
              src={image.url}
              alt={image.alt_text || product.title}
              className="size-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
              loading="lazy"
            />
          ) : (
            <CraftTile
              craftSlug={product.craft.slug}
              seedKey={product.slug}
              className="size-full transition-transform duration-300 group-hover:scale-[1.03]"
            />
          )}

          {!product.in_stock && (
            <Badge
              variant="secondary"
              className="absolute top-3 left-3 rounded-full"
            >
              Sold out
            </Badge>
          )}
        </div>

        <div className="mt-3 space-y-1">
          <p className="text-xs font-semibold tracking-wide uppercase opacity-60">
            {product.craft.name}
          </p>
          <h3 className="leading-snug font-semibold text-balance group-hover:underline">
            {product.title}
          </h3>
          <p className="text-sm opacity-70">
            {product.artisan.display_name} ·{" "}
            {product.origin_district || product.artisan.district}
          </p>
          <p className="pt-1 font-semibold">
            {formatMoney(product.price_minor, product.currency)}
          </p>
        </div>
      </Link>
    </article>
  );
}
