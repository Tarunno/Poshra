/**
 * Server-side access to the checkout API: the cart, and orders.
 *
 * As with the catalog, every call goes through Kong. The difference is that
 * these routes demand a session — the gateway rejects anything it cannot
 * verify — so the browser's cookie has to be forwarded deliberately. A fetch
 * on the server has no cookie jar of its own to inherit one from.
 */
import { cache } from "react";
import { cookies } from "next/headers";

const CHECKOUT_BASE =
  process.env.CHECKOUT_BASE_URL ?? "http://localhost:8080/api/checkout";

export type CartLine = {
  sku_id: string;
  quantity: number;
  title: string;
  unit_minor: number;
  line_minor: number;
  currency: string;
  artisan_name: string;
  /** False once a piece has been withdrawn or sold out since it was added. */
  available: boolean;
};

export type Cart = {
  items: CartLine[];
  total_minor: number;
  currency: string;
};

export const EMPTY_CART: Cart = { items: [], total_minor: 0, currency: "BDT" };

export async function checkoutFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const cookieHeader = (await cookies()).toString();
  return fetch(`${CHECKOUT_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      ...(cookieHeader ? { cookie: cookieHeader } : {}),
    },
    // A cart is per-buyer and changes constantly; nothing here may be cached.
    cache: "no-store",
  });
}

/**
 * The signed-in buyer's cart, or null when there is no session.
 *
 * Wrapped in React's cache so the header and the page below it share a single
 * request per render rather than asking the gateway twice for the same thing.
 * Anything other than a missing session throws: an unreachable checkout
 * service must not be rendered as "your cart is empty".
 */
export const getCart = cache(async (): Promise<Cart | null> => {
  const response = await checkoutFetch("/cart");
  if (response.status === 401) return null;
  if (!response.ok) throw new Error(`cart request failed: ${response.status}`);
  return (await response.json()) as Cart;
});

/** The same, for places where a failure must not take the page down. */
export async function getCartQuietly(): Promise<Cart | null> {
  try {
    return await getCart();
  } catch {
    return null;
  }
}

export type OrderItem = {
  sku_id: string;
  quantity: number;
  unit_minor: number;
  title: string;
  artisan_name: string;
};

export type Order = {
  id: string;
  status: string;
  total_minor: number;
  currency: string;
  reservation_id: string;
  payment_ref?: string;
  failure_reason?: string;
  created_at: string;
  items: OrderItem[];
};

/** One order, or null when it is not this buyer's. */
export async function getOrder(id: string): Promise<Order | null> {
  const response = await checkoutFetch(`/orders/${encodeURIComponent(id)}`);
  // Someone else's order answers 404, never 403: the difference would confirm
  // that it exists.
  if (response.status === 404 || response.status === 401) return null;
  if (!response.ok) throw new Error(`order request failed: ${response.status}`);
  return (await response.json()) as Order;
}

export function cartCount(cart: Cart | null): number {
  return cart?.items.reduce((total, line) => total + line.quantity, 0) ?? 0;
}
