import Link from "next/link";
import { redirect } from "next/navigation";
import { Minus, Plus, ShoppingBag, Trash2, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { KanthaRule } from "@/components/motifs";
import { getCurrentUser } from "@/lib/api";
import {
  clearCartAction,
  removeItemAction,
  setQuantityAction,
} from "@/lib/cart-actions";
import { EMPTY_CART, getCart, type CartLine } from "@/lib/checkout";
import { formatMoney } from "@/lib/format";

export const metadata = { title: "Your cart — Poshra" };

/** One quantity step, as a form so it needs no client JavaScript. */
function StepButton({
  skuId,
  quantity,
  label,
  children,
}: {
  skuId: string;
  quantity: number;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <form action={setQuantityAction}>
      <input type="hidden" name="sku_id" value={skuId} />
      <input type="hidden" name="quantity" value={quantity} />
      <Button
        type="submit"
        variant="ghost"
        size="icon"
        className="size-8 rounded-full"
        aria-label={label}
      >
        {children}
      </Button>
    </form>
  );
}

function CartRow({ line }: { line: CartLine }) {
  return (
    <li className="flex flex-wrap items-center gap-4 py-5">
      <div className="min-w-48 flex-1">
        {line.available ? (
          <>
            <p className="font-semibold">{line.title}</p>
            <p className="text-sm opacity-70">by {line.artisan_name}</p>
          </>
        ) : (
          <p className="text-ink-rose flex items-center gap-1.5 font-medium">
            <TriangleAlert className="size-4" aria-hidden />
            This piece is no longer available
          </p>
        )}
      </div>

      <div className="bg-background/70 flex items-center gap-1 rounded-full p-1">
        <StepButton
          skuId={line.sku_id}
          quantity={line.quantity - 1}
          label={`Reduce the quantity of ${line.title || "this piece"}`}
        >
          <Minus className="size-3.5" aria-hidden />
        </StepButton>
        <span className="w-7 text-center text-sm font-semibold tabular-nums">
          {line.quantity}
        </span>
        <StepButton
          skuId={line.sku_id}
          quantity={line.quantity + 1}
          label={`Increase the quantity of ${line.title || "this piece"}`}
        >
          <Plus className="size-3.5" aria-hidden />
        </StepButton>
      </div>

      <p className="w-28 text-right font-semibold tabular-nums">
        {line.available ? formatMoney(line.line_minor, line.currency) : "—"}
      </p>

      <form action={removeItemAction}>
        <input type="hidden" name="sku_id" value={line.sku_id} />
        <Button
          type="submit"
          variant="ghost"
          size="icon"
          className="size-8 rounded-full opacity-60 hover:opacity-100"
          aria-label={`Remove ${line.title || "this piece"} from your cart`}
        >
          <Trash2 className="size-4" aria-hidden />
        </Button>
      </form>
    </li>
  );
}

export default async function CartPage() {
  // The cart belongs to a buyer, so there is nothing to show without one.
  if (!(await getCurrentUser())) redirect("/login?next=%2Fcart");

  const cart = (await getCart()) ?? EMPTY_CART;
  const unavailable = cart.items.some((line) => !line.available);

  if (cart.items.length === 0) {
    return (
      <div className="bg-tint-sky rounded-panel stitched p-9 text-center">
        <ShoppingBag className="mx-auto size-8 opacity-40" aria-hidden />
        <h1 className="mt-4 text-2xl font-extrabold tracking-tight">
          Your cart is empty.
        </h1>
        <p className="mt-2 text-sm opacity-70">
          Every piece on Poshra is made by hand, one at a time.
        </p>
        <Button asChild size="lg" className="mt-6 rounded-full px-7">
          <Link href="/shop">Browse the shop</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-extrabold tracking-tight">Your cart</h1>

      <section className="bg-tint-saffron rounded-panel stitched p-6 sm:p-8">
        <ul className="divide-foreground/10 divide-y">
          {cart.items.map((line) => (
            <CartRow key={line.sku_id} line={line} />
          ))}
        </ul>

        <KanthaRule className="my-6 h-3 w-full opacity-50" />

        <div className="flex flex-wrap items-center justify-between gap-4">
          <form action={clearCartAction}>
            <Button
              type="submit"
              variant="ghost"
              size="sm"
              className="rounded-full opacity-70 hover:opacity-100"
            >
              Empty the cart
            </Button>
          </form>

          <div className="text-right">
            <p className="text-xs tracking-wide uppercase opacity-60">Total</p>
            <p className="text-2xl font-extrabold tabular-nums">
              {formatMoney(cart.total_minor, cart.currency)}
            </p>
          </div>
        </div>
      </section>

      {unavailable && (
        <p className="text-ink-rose flex items-center gap-2 text-sm font-medium">
          <TriangleAlert className="size-4" aria-hidden />
          Remove the pieces that are no longer available before checking out.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-4">
        {/* Step two of the buy flow. Disabled rather than hidden so the path
            through the page is obvious while it is being built. */}
        <Button size="lg" className="rounded-full px-7" disabled>
          Continue to checkout
        </Button>
        <Link
          href="/shop"
          className="text-sm font-semibold underline underline-offset-4"
        >
          Keep browsing
        </Link>
      </div>
    </div>
  );
}
