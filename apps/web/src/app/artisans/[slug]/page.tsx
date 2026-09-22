import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { BadgeCheck, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ProductGrid } from "@/components/product-grid";
import { getArtisan, listProducts } from "@/lib/catalog";

type Params = Promise<{ slug: string }>;

export async function generateMetadata({
  params,
}: {
  params: Params;
}): Promise<Metadata> {
  const { slug } = await params;
  const artisan = await getArtisan(slug);
  if (!artisan) return { title: "Artisan not found — Poshra" };

  return {
    title: `${artisan.display_name} — Poshra`,
    description:
      artisan.story.slice(0, 155) ||
      `${artisan.display_name} makes ${artisan.crafts.map((c) => c.name).join(", ")} in ${artisan.district}.`,
  };
}

export default async function ArtisanPage({ params }: { params: Params }) {
  const { slug } = await params;
  const artisan = await getArtisan(slug);
  if (!artisan) notFound();

  const products = await listProducts({ artisan: slug, limit: 24 });

  return (
    <div className="space-y-12">
      <header className="bg-tint-lilac rounded-panel stitched p-7 sm:p-10">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
            {artisan.display_name}
          </h1>
          {artisan.is_verified && (
            <Badge className="text-ink-lilac bg-background gap-1 rounded-full">
              <BadgeCheck className="size-3.5" aria-hidden /> Verified artisan
            </Badge>
          )}
        </div>

        <p className="mt-3 flex items-center gap-1.5 text-sm opacity-70">
          <MapPin className="size-4" aria-hidden />
          {artisan.district}, {artisan.division}
        </p>

        {artisan.story && (
          <p className="mt-5 max-w-2xl leading-relaxed text-pretty opacity-80">
            {artisan.story}
          </p>
        )}

        {artisan.crafts.length > 0 && (
          <nav aria-label="Crafts" className="mt-6 flex flex-wrap gap-2">
            {artisan.crafts.map((craft) => (
              <Link
                key={craft.slug}
                href={`/shop?craft=${craft.slug}`}
                className="bg-background rounded-full px-4 py-1.5 text-sm font-medium hover:opacity-80"
              >
                {craft.name}
                <span className="font-bangla ml-1.5 opacity-70">
                  {craft.name_bn}
                </span>
              </Link>
            ))}
          </nav>
        )}
      </header>

      <section className="space-y-6">
        <h2 className="text-2xl font-bold tracking-tight">
          {products.count > 0
            ? `${products.count} ${products.count === 1 ? "piece" : "pieces"} from this workshop`
            : "No pieces listed yet"}
        </h2>
        {products.count > 0 && <ProductGrid products={products.results} />}
      </section>
    </div>
  );
}
