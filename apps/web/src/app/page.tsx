import Link from "next/link";
import { Bot, Camera, HandHeart, MapPin, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CraftScene } from "@/components/craft-scene";
import { MakersHand, NeedleThread, Weave } from "@/components/motifs";
import { TintedCard } from "@/components/tinted-card";
import { getCurrentUser } from "@/lib/api";

export default async function HomePage() {
  const user = await getCurrentUser();

  return (
    <div className="space-y-8">
      <section className="relative grid items-center gap-8 px-1 pt-4 pb-2 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <span className="bg-tint-mint text-ink-mint inline-flex -rotate-2 items-center gap-2 rounded-full px-4 py-1.5 text-sm font-semibold">
            <span className="font-bangla">পসরা</span> · a trader&apos;s spread
            of goods
          </span>

          <h1 className="mt-6 max-w-4xl text-[2.6rem] leading-[1.03] font-extrabold tracking-tight text-balance sm:text-6xl">
            Crafts from Bangladesh,
            <br className="hidden sm:block" />{" "}
            <span className="relative inline-block">
              sold the way they deserve.
              <span
                aria-hidden
                className="bg-tint-saffron absolute inset-x-0 -bottom-1 -z-10 h-3 rounded-full sm:h-4"
              />
            </span>
          </h1>

          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-pretty opacity-75">
            A weaver in Narayanganj photographs a saree and says a few words in
            Bangla. Poshra writes the listing, prices it, and puts it in front
            of a buyer in Berlin.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            {user ? (
              <Button asChild size="lg" className="rounded-full px-7 text-base">
                <Link href="/dashboard">Go to dashboard</Link>
              </Button>
            ) : (
              <>
                <Button
                  asChild
                  size="lg"
                  className="rounded-full px-7 text-base"
                >
                  <Link href="/register">Start selling</Link>
                </Button>
                <Button
                  asChild
                  size="lg"
                  variant="outline"
                  className="rounded-full border-2 px-7 text-base"
                >
                  <Link href="/login">Sign in</Link>
                </Button>
              </>
            )}
            <span className="text-sm opacity-60">
              Free to join · no listing fees
            </span>
          </div>

          <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm opacity-70">
            <span className="flex items-center gap-2">
              <Weave className="size-5" /> Handloom
            </span>
            <span className="flex items-center gap-2">
              <NeedleThread className="size-5" /> Hand-stitched
            </span>
            <span className="flex items-center gap-2">
              <MakersHand className="size-5" /> Artisan-owned
            </span>
          </div>
        </div>

        <CraftScene className="rounded-panel bg-background w-full" />
      </section>

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <TintedCard
          color="saffron"
          icon={Camera}
          eyebrow="For artisans"
          title="Photo in. Listing out."
          body="Upload a picture and describe the piece in Bangla. Get an English title, description, materials, craft background and a suggested price."
          href="/register"
          cta="Start selling"
          className="lg:col-span-2"
        />
        <TintedCard
          color="lilac"
          icon={Bot}
          eyebrow="For buyers"
          title="Shop by conversation."
          body="“A handmade wedding gift under $80 that ships to Germany.” Real products, not keyword soup."
          href="/register"
          cta="Create an account"
        />
        <TintedCard
          color="mint"
          icon={MapPin}
          eyebrow="Provenance"
          title="Every craft keeps its place."
          body="Jamdani from Narayanganj. Nakshi kantha from Jamalpur. Terracotta from Dhamrai."
        />
        <TintedCard
          color="rose"
          icon={Sparkles}
          eyebrow="Agent ready"
          title="Shoppable by AI agents."
          body="An MCP server exposes search, carts and orders, so an assistant can buy for a customer — with confirmation before anything is ordered."
        />
        <TintedCard
          color="sky"
          icon={HandHeart}
          eyebrow="Fair trade"
          title="The maker keeps the margin."
          body="Artisan-owned profiles, transparent pricing, payouts that reach the person who made the work."
        />
      </div>
    </div>
  );
}
