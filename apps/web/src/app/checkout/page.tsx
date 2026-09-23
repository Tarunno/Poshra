import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { KanthaRule } from "@/components/motifs";
import { PlaceOrder } from "@/components/place-order";
import { getCurrentUser } from "@/lib/api";
import { getCart } from "@/lib/checkout";
import { formatMoney } from "@/lib/format";

export const metadata = { title: "Checkout — Poshra" };

export default async function CheckoutPage() {
  if (!(await getCurrentUser())) redirect("/login?next=%2Fcheckout");

  const cart = await getCart();
  // Nothing to pay for, or something in the cart changed: the cart page is
  // where both of those are explained and fixed.
  if (!cart || cart.items.length === 0) redirect("/cart");
  if (cart.items.some((line) => !line.available)) redirect("/cart");

  // Minted once per render of this page. Every submission of the form below
  // carries it, so a double click or a refreshed POST is recognised as the
  // same attempt rather than a second order.
  const idempotencyKey = crypto.randomUUID();
  const total = formatMoney(cart.total_minor, cart.currency);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/cart"
          className="inline-flex items-center gap-1 text-sm font-semibold opacity-70 underline-offset-4 hover:underline hover:opacity-100"
        >
          <ArrowLeft className="size-4" aria-hidden />
          Cart
        </Link>
      </div>

      <h1 className="text-3xl font-extrabold tracking-tight">Checkout</h1>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <section className="bg-tint-mint rounded-panel stitched p-6 sm:p-8">
          <h2 className="text-sm font-semibold tracking-wide uppercase opacity-70">
            Your order
          </h2>

          <ul className="divide-foreground/10 mt-4 divide-y">
            {cart.items.map((line) => (
              <li
                key={line.sku_id}
                className="flex items-baseline gap-4 py-4 text-sm"
              >
                <div className="flex-1">
                  <p className="font-semibold">{line.title}</p>
                  <p className="opacity-70">by {line.artisan_name}</p>
                </div>
                <p className="tabular-nums opacity-70">× {line.quantity}</p>
                <p className="w-28 text-right font-semibold tabular-nums">
                  {formatMoney(line.line_minor, line.currency)}
                </p>
              </li>
            ))}
          </ul>

          <KanthaRule className="my-5 h-3 w-full opacity-50" />

          <div className="flex items-baseline justify-between">
            <span className="text-sm font-semibold">Total</span>
            <span className="text-2xl font-extrabold tabular-nums">
              {total}
            </span>
          </div>
          <p className="mt-2 text-xs opacity-60">
            Stock is held while your payment is processed, and released
            automatically if it does not complete.
          </p>
        </section>

        <section className="bg-tint-lilac rounded-panel stitched h-fit p-6 sm:p-8">
          <PlaceOrder idempotencyKey={idempotencyKey} total={total} />
        </section>
      </div>
    </div>
  );
}
