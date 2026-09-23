import Image from "next/image";
import Link from "next/link";

import { CraftTile } from "@/components/craft-tile";
import type { Product } from "@/lib/catalog";
import { formatMoney } from "@/lib/format";

/**
 * One of the artisan's own pieces.
 *
 * Denser than the storefront card and weighted differently: an artisan looking
 * at their workshop needs to see stock and whether it is live, where a shopper
 * needs the maker and the place.
 */
export function WorkshopPiece({ product }: { product: Product }) {
  const image = product.images[0];
  const out = product.stock === 0;

  return (
    <Link
      href={`/products/${product.slug}`}
      className="group focus-visible:ring-foreground/50 block rounded-2xl focus-visible:ring-2 focus-visible:ring-offset-4 focus-visible:outline-none"
    >
      <div className="relative aspect-square overflow-hidden rounded-2xl">
        {image ? (
          <Image
            src={image.url}
            alt={image.alt_text || product.title}
            fill
            sizes="(min-width: 1024px) 18vw, 40vw"
            className="object-cover transition-transform duration-300 group-hover:scale-[1.04]"
          />
        ) : (
          <CraftTile
            craftSlug={product.craft.slug}
            seedKey={product.slug}
            className="size-full"
          />
        )}

        <span
          className={`absolute bottom-2 left-2 rounded-full px-2.5 py-1 text-[0.7rem] font-semibold tabular-nums backdrop-blur ${
            out
              ? "bg-ink-rose text-background"
              : "bg-background/85 text-foreground"
          }`}
        >
          {out ? "Out of stock" : `${product.stock} left`}
        </span>

        {product.status !== "published" && (
          <span className="bg-background/85 absolute top-2 left-2 rounded-full px-2.5 py-1 text-[0.7rem] font-semibold capitalize backdrop-blur">
            {product.status}
          </span>
        )}
      </div>

      <p className="mt-2 line-clamp-1 text-sm font-semibold group-hover:underline">
        {product.title}
      </p>
      <p className="text-xs tabular-nums opacity-70">
        {formatMoney(product.price_minor, product.currency)}
      </p>
    </Link>
  );
}
