import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { Hind_Siliguri } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { AssistantWidget } from "@/components/assistant-widget";
import { SessionKeeper } from "@/components/session-keeper";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { getCurrentUser } from "@/lib/api";
import { cartCount, getCartQuietly } from "@/lib/checkout";
import "./globals.css";

const sans = Geist({ variable: "--font-sans", subsets: ["latin"] });
// Bengali script needs its own face; artisan names and craft terms use it.
const bangla = Hind_Siliguri({
  variable: "--font-bangla",
  subsets: ["bengali"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Poshra — crafts from Bangladesh",
  description:
    "An agent-ready marketplace connecting Bangladeshi artisans with buyers worldwide.",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Server Component: the session is read on the server, so the token never
  // reaches client JavaScript.
  const user = await getCurrentUser();
  // Quietly: a checkout outage should cost the buyer their cart badge, not
  // every page on the site.
  const items = user ? cartCount(await getCartQuietly()) : 0;

  return (
    <html lang="en">
      <body
        className={`${sans.variable} ${bangla.variable} font-sans antialiased`}
      >
        {user && <SessionKeeper />}
        <SiteHeader user={user} cartCount={items} />
        <main className="mx-auto w-full max-w-6xl px-4 py-10">{children}</main>
        <SiteFooter />
        {/* Signed in only: every answer is a paid model call, and the route
            behind it requires a session anyway. */}
        {user && <AssistantWidget />}
        <Toaster />
      </body>
    </html>
  );
}
