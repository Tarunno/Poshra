import Image from "next/image";
import Link from "next/link";
import { CardActions } from "@/components/card-actions";
import { CraftTile } from "@/components/craft-tile";
import { Badge } from "@/components/ui/badge";
import type { Product } from "@/lib/catalog";
import { formatMoney } from "@/lib/format";

export function ProductCard({
  product,
  saved = false,
  actions = false,
  layout = "tile",
}: {
  product: Product;
  saved?: boolean;
  /** Off by default: a card inside a chat answer is for reading, not acting. */
  actions?: boolean;
  /**
   * "row" is for narrow places — the assistant panel is about 380px wide, and
   * a tile's 4:5 photograph fills the whole of it, so one suggestion pushes
   * the next off the screen. A row gives the photograph a thumbnail and lets
   * three pieces be read at a glance.
   */
  layout?: "tile" | "row";
}) {
  const image = product.images[0];

  if (layout === "row") {
    return (
      <article className="group">
        <Link
          href={`/products/${product.slug}`}
          className="focus-visible:ring-foreground/50 hover:bg-muted/50 flex items-center gap-3 rounded-2xl p-2 transition-colors focus-visible:ring-2 focus-visible:outline-none"
        >
          <div className="relative size-16 shrink-0 overflow-hidden rounded-xl">
            {image ? (
              <Image
                src={image.url}
                alt={image.alt_text || product.title}
                fill
                sizes="64px"
                className="object-cover"
              />
            ) : (
              <CraftTile
                craftSlug={product.craft.slug}
                seedKey={product.slug}
                className="size-full"
              />
            )}
          </div>

          <div className="min-w-0 flex-1">
            <h3 className="truncate text-sm leading-snug font-semibold group-hover:underline">
              {product.title}
            </h3>
            <p className="truncate text-xs opacity-70">
              {product.artisan.display_name} ·{" "}
              {product.origin_district || product.artisan.district}
            </p>
            <p className="text-sm font-semibold">
              {formatMoney(product.price_minor, product.currency)}
              {!product.in_stock && (
                <span className="ml-2 text-xs font-normal opacity-60">
                  Sold out
                </span>
              )}
            </p>
          </div>
        </Link>
      </article>
    );
  }

  return (
    <article className="group relative">
      <Link
        href={`/products/${product.slug}`}
        className="focus-visible:ring-foreground/50 block rounded-3xl focus-visible:ring-2 focus-visible:ring-offset-4 focus-visible:outline-none"
      >
        <div className="rounded-3xl relative aspect-[4/5] overflow-hidden">
          {image ? (
            <Image
              src={image.url}
              alt={image.alt_text || product.title}
              fill
              // Two columns on small screens, three from lg: tell the optimiser
              // so it serves a sensibly sized file instead of the full width.
              sizes="(min-width: 1024px) 30vw, 45vw"
              className="object-cover transition-transform duration-300 group-hover:scale-[1.03]"
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

      {actions && (
        <CardActions
          skuId={product.id}
          slug={product.slug}
          saved={saved}
          inStock={product.in_stock}
        />
      )}
    </article>
  );
}
