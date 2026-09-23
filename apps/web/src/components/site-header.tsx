import Link from "next/link";
import { ShoppingBag, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PoshraLogo } from "@/components/logo";
import { KanthaRule } from "@/components/motifs";
import { UserMenu } from "@/components/user-menu";
import type { User } from "@/lib/api";

export function SiteHeader({
  user,
  cartCount = 0,
}: {
  user: User | null;
  cartCount?: number;
}) {
  return (
    <header className="bg-tint-saffron/60 sticky top-0 z-40 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-4">
        <Link href="/" aria-label="Poshra home">
          <PoshraLogo className="flex items-center gap-2.5" />
        </Link>

        <nav className="flex items-center gap-2">
          <Button asChild variant="ghost" size="sm" className="rounded-full">
            <Link href="/shop">Shop</Link>
          </Button>
          {user && (
            <Button asChild variant="ghost" size="sm" className="rounded-full">
              <Link href="/assistant">
                <Sparkles className="size-4" aria-hidden />
                <span className="hidden sm:inline">Ask</span>
              </Link>
            </Button>
          )}
          {user ? (
            <>
              <Button
                asChild
                variant="ghost"
                size="sm"
                className="relative rounded-full"
              >
                <Link href="/cart" aria-label={`Cart, ${cartCount} items`}>
                  <ShoppingBag className="size-4" aria-hidden />
                  <span className="hidden sm:inline">Cart</span>
                  {cartCount > 0 && (
                    <span className="bg-foreground text-background grid size-5 place-items-center rounded-full text-[0.7rem] font-bold tabular-nums">
                      {cartCount}
                    </span>
                  )}
                </Link>
              </Button>
              {user.role === "artisan" && (
                <Badge
                  variant="secondary"
                  className="hidden rounded-full sm:inline-flex"
                >
                  Artisan
                </Badge>
              )}
              <Button
                asChild
                variant="ghost"
                size="sm"
                className="rounded-full"
              >
                <Link href="/dashboard">Dashboard</Link>
              </Button>
              <UserMenu user={user} />
            </>
          ) : (
            <>
              <span className="text-foreground/70 hidden text-sm sm:inline">
                New to Poshra?
              </span>
              <Button
                asChild
                variant="ghost"
                size="sm"
                className="rounded-full"
              >
                <Link href="/login">Sign in</Link>
              </Button>
              <Button asChild size="sm" className="rounded-full px-5">
                <Link href="/register">Create a free account</Link>
              </Button>
            </>
          )}
        </nav>
      </div>
      <KanthaRule className="h-3 w-full opacity-60" />
    </header>
  );
}
