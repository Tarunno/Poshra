import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { Hind_Siliguri } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { SessionKeeper } from "@/components/session-keeper";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { getCurrentUser } from "@/lib/api";
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

  return (
    <html lang="en">
      <body
        className={`${sans.variable} ${bangla.variable} font-sans antialiased`}
      >
        {user && <SessionKeeper />}
        <SiteHeader user={user} />
        <main className="mx-auto w-full max-w-6xl px-4 py-10">{children}</main>
        <SiteFooter />
        <Toaster />
      </body>
    </html>
  );
}
