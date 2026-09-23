import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { BadgeCheck, MapPin, Package, Ruler } from "lucide-react";
import { AddToCart } from "@/components/add-to-cart";
import { CraftTile } from "@/components/craft-tile";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { KanthaRule } from "@/components/motifs";
import { ProductGrid } from "@/components/product-grid";
import { getProduct, listProducts } from "@/lib/catalog";
import { formatLeadTime, formatMoney } from "@/lib/format";

type Params = Promise<{ slug: string }>;

/** Per-page metadata: a listing shared in a chat or a search result needs its own title. */
export async function generateMetadata({
  params,
}: {
  params: Params;
}): Promise<Metadata> {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) return { title: "Piece not found — Poshra" };

  const description =
    product.description.slice(0, 155) ||
    `${product.craft.name} by ${product.artisan.display_name}, ${product.artisan.district}.`;

  return {
    title: `${product.title} — Poshra`,
    description,
    openGraph: {
      title: product.title,
      description,
      type: "website",
      images: product.images[0] ? [{ url: product.images[0].url }] : undefined,
    },
  };
}

export default async function ProductPage({ params }: { params: Params }) {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) notFound();

  // More from the same craft, minus this piece.
  const related = await listProducts({ craft: product.craft.slug, limit: 4 });
  const others = related.results
    .filter((item) => item.id !== product.id)
    .slice(0, 3);

  const image = product.images[0];

  return (
    <div className="space-y-16">
      <nav aria-label="Breadcrumb" className="text-sm opacity-70">
        <Link href="/shop" className="hover:underline">
          Shop
        </Link>{" "}
        ·{" "}
        <Link
          href={`/shop?craft=${product.craft.slug}`}
          className="hover:underline"
        >
          {product.craft.name}
        </Link>
      </nav>

      <div className="grid gap-10 lg:grid-cols-2">
        <figure className="space-y-2">
          <div className="rounded-panel relative aspect-[4/5] overflow-hidden">
            {image ? (
              <Image
                src={image.url}
                alt={image.alt_text || product.title}
                fill
                priority
                sizes="(min-width: 1024px) 45vw, 100vw"
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
          {image?.credit && (
            <figcaption className="text-xs opacity-60">
              Photograph:{" "}
              <a
                href={image.credit_url}
                className="underline underline-offset-2"
                rel="nofollow"
              >
                {image.credit}
              </a>
              {image.license && ` · ${image.license}`}
            </figcaption>
          )}
        </figure>

        <div className="space-y-6">
          <div className="space-y-3">
            <Link
              href={`/shop?craft=${product.craft.slug}`}
              className="text-xs font-semibold tracking-wide uppercase opacity-60 hover:underline"
            >
              {product.craft.name}
            </Link>
            <h1 className="text-3xl font-extrabold tracking-tight text-balance sm:text-4xl">
              {product.title}
            </h1>
            <p className="text-2xl font-semibold">
              {formatMoney(product.price_minor, product.currency)}
            </p>
          </div>

          {product.description && (
            <p className="leading-relaxed text-pretty opacity-80">
              {product.description}
            </p>
          )}

          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            {product.materials && (
              <div className="flex items-start gap-2">
                <Package
                  className="mt-0.5 size-4 shrink-0 opacity-60"
                  aria-hidden
                />
                <div>
                  <dt className="font-medium">Materials</dt>
                  <dd className="opacity-70">{product.materials}</dd>
                </div>
              </div>
            )}
            {product.dimensions && (
              <div className="flex items-start gap-2">
                <Ruler
                  className="mt-0.5 size-4 shrink-0 opacity-60"
                  aria-hidden
                />
                <div>
                  <dt className="font-medium">Dimensions</dt>
                  <dd className="opacity-70">{product.dimensions}</dd>
                </div>
              </div>
            )}
            {(product.origin_district || product.artisan.district) && (
              <div className="flex items-start gap-2">
                <MapPin
                  className="mt-0.5 size-4 shrink-0 opacity-60"
                  aria-hidden
                />
                <div>
                  <dt className="font-medium">Made in</dt>
                  <dd className="opacity-70">
                    {product.origin_district || product.artisan.district}
                  </dd>
                </div>
              </div>
            )}
            <div className="flex items-start gap-2">
              <Package
                className="mt-0.5 size-4 shrink-0 opacity-60"
                aria-hidden
              />
              <div>
                <dt className="font-medium">Availability</dt>
                <dd className="opacity-70">
                  {product.in_stock
                    ? `${formatLeadTime(product.lead_time_days)} · ${product.stock} available`
                    : "Sold out — ask the artisan about a commission"}
                </dd>
              </div>
            </div>
          </dl>

          <div className="pt-2">
            {product.in_stock ? (
              <AddToCart
                skuId={product.id}
                back={`/products/${product.slug}`}
                max={product.stock}
              />
            ) : (
              <div className="flex flex-wrap gap-3">
                <Button size="lg" className="rounded-full px-7" disabled>
                  Sold out
                </Button>
                <Badge variant="outline" className="self-center rounded-full">
                  Ask about a commission
                </Badge>
              </div>
            )}
          </div>

          <KanthaRule className="h-4 w-full opacity-50" />

          <section className="bg-tint-mint rounded-panel stitched p-6">
            <h2 className="flex items-center gap-2 font-semibold">
              {product.artisan.display_name}
              {product.artisan.is_verified && (
                <BadgeCheck
                  className="text-ink-mint size-4"
                  aria-label="Verified artisan"
                />
              )}
            </h2>
            <p className="mt-1 text-sm opacity-70">
              {product.artisan.district}, {product.artisan.division}
            </p>
            <Link
              href={`/artisans/${product.artisan.slug}`}
              className="mt-4 inline-block text-sm font-semibold underline underline-offset-4"
            >
              Visit the workshop
            </Link>
          </section>
        </div>
      </div>

      {product.craft.description && (
        <section className="bg-tint-saffron rounded-panel stitched p-7 sm:p-9">
          <h2 className="text-2xl font-bold tracking-tight">
            About {product.craft.name}
            <span className="font-bangla ml-2 text-lg opacity-60">
              {product.craft.name_bn}
            </span>
          </h2>
          <p className="mt-3 max-w-3xl leading-relaxed text-pretty opacity-80">
            {product.craft.description}
          </p>
        </section>
      )}

      {others.length > 0 && (
        <section className="space-y-6">
          <h2 className="text-2xl font-bold tracking-tight">
            More {product.craft.name}
          </h2>
          <ProductGrid products={others} />
        </section>
      )}

      {/* Structured data: lets search engines and AI agents read the listing. */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Product",
            name: product.title,
            description: product.description,
            category: product.craft.name,
            material: product.materials || undefined,
            brand: { "@type": "Brand", name: product.artisan.display_name },
            offers: {
              "@type": "Offer",
              price: (product.price_minor / 100).toFixed(2),
              priceCurrency: product.currency,
              availability: product.in_stock
                ? "https://schema.org/InStock"
                : "https://schema.org/OutOfStock",
            },
          }),
        }}
      />
    </div>
  );
}
