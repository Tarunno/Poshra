import Link from "next/link";
import { redirect } from "next/navigation";
import { ShoppingBag } from "lucide-react";

import { Button } from "@/components/ui/button";
import { OrderSummary } from "@/components/order-summary";
import { getCurrentUser } from "@/lib/api";
import { listOrders } from "@/lib/checkout";

export const metadata = { title: "Your orders — Poshra" };

export default async function OrdersPage() {
  if (!(await getCurrentUser())) redirect("/login?next=%2Forders");

  const orders = await listOrders();

  if (orders.length === 0) {
    return (
      <div className="bg-tint-sky rounded-panel stitched p-9 text-center">
        <ShoppingBag className="mx-auto size-8 opacity-40" aria-hidden />
        <h1 className="mt-4 text-2xl font-extrabold tracking-tight">
          No orders yet.
        </h1>
        <p className="mt-2 text-sm opacity-70">
          When you buy a piece, it will appear here with its status.
        </p>
        <Button asChild size="lg" className="mt-6 rounded-full px-7">
          <Link href="/shop">Browse the shop</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-extrabold tracking-tight">Your orders</h1>
      <section className="bg-tint-saffron rounded-panel stitched p-6 sm:p-8">
        <ul className="divide-foreground/10 divide-y">
          {orders.map((order) => (
            <OrderSummary key={order.id} order={order} />
          ))}
        </ul>
      </section>
    </div>
  );
}
