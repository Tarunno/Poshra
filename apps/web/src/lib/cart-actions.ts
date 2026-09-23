"use server";

/**
 * Server Actions for the cart.
 *
 * Each one is a plain form submission, so the cart works with JavaScript
 * disabled and keeps working while a page is still hydrating. A Server Action
 * is a public POST endpoint, so quantities are validated here and the identity
 * comes from the cookie by way of the gateway — never from the form.
 */
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { checkoutFetch } from "./checkout";
import { safePath } from "./safe-path";

export type AddToCartState = { error?: string; added?: boolean };

const MAX_PER_PIECE = 20;

/**
 * The cart count lives in the site header, which is part of the root layout,
 * so a change has to refresh the layout and not just the page that caused it.
 */
function refreshCart() {
  revalidatePath("/", "layout");
}

async function signInFirst(back: string): Promise<never> {
  redirect(`/login?next=${encodeURIComponent(back)}`);
}

export async function addToCartAction(
  _prev: AddToCartState,
  formData: FormData,
): Promise<AddToCartState> {
  const skuId = String(formData.get("sku_id") ?? "");
  const quantity = Number(formData.get("quantity") ?? 1);
  const back = safePath(String(formData.get("back") ?? ""), "/cart");

  if (!Number.isInteger(quantity) || quantity < 1 || quantity > MAX_PER_PIECE) {
    return { error: `Choose between 1 and ${MAX_PER_PIECE}.` };
  }

  const response = await checkoutFetch("/cart/items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sku_id: skuId, quantity }),
  });

  // The session expired between loading the page and pressing the button.
  if (response.status === 401) await signInFirst(back);

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    return { error: body.detail ?? "Could not add this piece to your cart." };
  }

  refreshCart();
  return { added: true };
}

export async function setQuantityAction(formData: FormData): Promise<void> {
  const skuId = String(formData.get("sku_id") ?? "");
  const quantity = Number(formData.get("quantity") ?? 0);
  // Zero is meaningful: the API removes the line rather than storing nothing.
  if (!Number.isInteger(quantity) || quantity < 0 || quantity > MAX_PER_PIECE) {
    return;
  }

  const response = await checkoutFetch(
    `/cart/items/${encodeURIComponent(skuId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quantity }),
    },
  );
  if (response.status === 401) await signInFirst("/cart");
  refreshCart();
}

export async function removeItemAction(formData: FormData): Promise<void> {
  const skuId = String(formData.get("sku_id") ?? "");
  const response = await checkoutFetch(
    `/cart/items/${encodeURIComponent(skuId)}`,
    { method: "DELETE" },
  );
  if (response.status === 401) await signInFirst("/cart");
  refreshCart();
}

export async function clearCartAction(): Promise<void> {
  const response = await checkoutFetch("/cart", { method: "DELETE" });
  if (response.status === 401) await signInFirst("/cart");
  refreshCart();
}
