"use server";

/**
 * Placing an order.
 *
 * The saga behind this reserves stock, charges, and writes the order with its
 * event in one transaction. From the browser's side the only thing that
 * matters is that pressing the button twice must not buy the thing twice,
 * which is what the idempotency key is for.
 */
import { redirect } from "next/navigation";

import { checkoutFetch } from "./checkout";

export type PlaceOrderState = { error?: string; backToCart?: boolean };

export async function placeOrderAction(
  _prev: PlaceOrderState,
  formData: FormData,
): Promise<PlaceOrderState> {
  // Minted when the page rendered and carried in a hidden field, so every
  // submission of *this* form — a double click, a refresh, a retried POST —
  // arrives with the same key and checkout replays its first answer instead of
  // charging again. Generating it here would defeat the point: each attempt
  // would look like a new order.
  const key = String(formData.get("idempotency_key") ?? "");
  if (!/^[0-9a-f-]{36}$/i.test(key)) {
    return { error: "This page is stale. Reload it and try again." };
  }

  // Only the outcome is chosen here; the amount comes from the cart, priced
  // server-side. A total posted by the browser would be a total the browser
  // could edit.
  const token =
    String(formData.get("outcome") ?? "approve") === "decline"
      ? "decline"
      : "test-card";

  const response = await checkoutFetch("/orders", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": key,
    },
    body: JSON.stringify({ payment_token: token }),
  });

  if (response.status === 401) redirect("/login?next=%2Fcheckout");

  if (response.ok) {
    const order = (await response.json()) as { id: string };
    redirect(`/orders/${order.id}`);
  }

  const body = (await response.json().catch(() => ({}))) as { detail?: string };

  switch (response.status) {
    case 402:
      // The hold was already released, so the cart is intact and another card
      // can be tried.
      return { error: body.detail ?? "The payment was declined." };
    case 409:
      return {
        error:
          body.detail ??
          "Something in your cart changed while you were checking out.",
        backToCart: true,
      };
    case 400:
      return { error: body.detail ?? "Your cart is empty.", backToCart: true };
    default:
      return { error: "Could not place the order. Please try again." };
  }
}
