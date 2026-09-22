import { redirect } from "next/navigation";
import { MessagesSquare, PackageOpen, ShoppingBag } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { TintedCard } from "@/components/tinted-card";
import { getCurrentUser } from "@/lib/api";

export const metadata = { title: "Dashboard — Poshra" };

export default async function DashboardPage() {
  const user = await getCurrentUser();
  // Server-side guard. The gateway enforces access too; this is for UX.
  if (!user) redirect("/login");

  const artisan = user.role === "artisan";

  return (
    <div className="space-y-6">
      <section className="px-1 pt-2">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          {user.full_name
            ? `Welcome, ${user.full_name.split(" ")[0]}.`
            : "Welcome."}
        </h1>
        <p className="text-foreground/70 mt-2 text-sm">
          {user.email}{" "}
          <Badge variant="secondary" className="ml-1 rounded-full">
            {user.role}
          </Badge>
        </p>
      </section>

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <TintedCard
          color="saffron"
          icon={PackageOpen}
          eyebrow={artisan ? "Your workshop" : "Browse"}
          title={artisan ? "Listings" : "Discover crafts"}
          body={
            artisan
              ? "Photograph a piece, describe it in Bangla, and publish a listing buyers can find."
              : "Handwoven, hand-painted and hand-thrown work from across Bangladesh."
          }
        >
          <Badge variant="outline" className="mt-5 rounded-full">
            Coming soon
          </Badge>
        </TintedCard>

        <TintedCard
          color="lilac"
          icon={ShoppingBag}
          eyebrow="Orders"
          title={artisan ? "Sales and shipping" : "Your orders"}
          body="Every order, its payment state and where the parcel is right now."
        >
          <Badge variant="outline" className="mt-5 rounded-full">
            Coming soon
          </Badge>
        </TintedCard>

        <TintedCard
          color="mint"
          icon={MessagesSquare}
          eyebrow="Assistant"
          title="Ask in plain language"
          body={
            artisan
              ? "“Which pieces sold best this month, and what should I make next?”"
              : "“Find me a nakshi kantha under $120 that ships to Canada.”"
          }
        >
          <Badge variant="outline" className="mt-5 rounded-full">
            Coming soon
          </Badge>
        </TintedCard>
      </div>
    </div>
  );
}
