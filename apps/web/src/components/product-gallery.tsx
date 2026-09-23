import Image from "next/image";

import { CraftTile } from "@/components/craft-tile";
import type { Product } from "@/lib/catalog";

/**
 * Every photograph of a piece, not just the first.
 *
 * A scroll-snapping row with anchor-link thumbnails, so it needs no
 * JavaScript and no state: the browser scrolls the row to the photograph whose
 * id the thumbnail names, and swiping works because it is an ordinary
 * horizontal scroll. The page that actually sells the piece should not depend
 * on hydration to show it.
 */
export function ProductGallery({ product }: { product: Product }) {
  const images = product.images;

  if (images.length === 0) {
    return (
      <div className="rounded-panel relative aspect-[4/5] overflow-hidden">
        <CraftTile
          craftSlug={product.craft.slug}
          seedKey={product.slug}
          className="size-full"
        />
      </div>
    );
  }

  const single = images.length === 1;

  return (
    <div className="space-y-3">
      <div
        className={`rounded-panel no-scrollbar flex ${
          // One photograph is not a carousel: no snapping, and nothing that
          // could show a scrollbar under a single static image.
          single ? "" : "snap-x snap-mandatory overflow-x-auto"
        }`}
        // A gallery is one figure; the thumbnails below navigate within it.
        aria-label={`Photographs of ${product.title}`}
      >
        {images.map((image, index) => (
          <div
            key={image.url}
            id={`photo-${index}`}
            className="relative aspect-[4/5] w-full shrink-0 snap-center"
          >
            <Image
              src={image.url}
              alt={
                image.alt_text || `${product.title}, photograph ${index + 1}`
              }
              fill
              // Only the first is above the fold; the rest load as they scroll.
              priority={index === 0}
              sizes="(min-width: 1024px) 45vw, 100vw"
              className="object-cover"
            />
          </div>
        ))}
      </div>

      {!single && (
        <ul className="flex flex-wrap gap-2">
          {images.map((image, index) => (
            <li key={`thumb-${image.url}`}>
              <a
                href={`#photo-${index}`}
                className="focus-visible:ring-foreground/50 relative block size-16 overflow-hidden rounded-xl opacity-70 transition hover:opacity-100 focus-visible:ring-2 focus-visible:outline-none"
              >
                <Image
                  src={image.url}
                  alt=""
                  fill
                  sizes="64px"
                  className="object-cover"
                />
                <span className="sr-only">
                  Show photograph {index + 1} of {images.length}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
