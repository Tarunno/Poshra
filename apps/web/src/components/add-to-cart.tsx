"use client";

import Link from "next/link";
import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { AlertCircle, Check, ShoppingBag } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { addToCartAction, type AddToCartState } from "@/lib/cart-actions";

function SubmitButton() {
  // The pending flag comes from the form, so there is no second piece of
  // state to keep in step with it.
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      size="lg"
      className="rounded-full px-7"
      disabled={pending}
    >
      <ShoppingBag className="size-4" aria-hidden />
      {pending ? "Adding…" : "Add to cart"}
    </Button>
  );
}

/**
 * The buy box.
 *
 * It is an ordinary form posting to a Server Action, so it works before React
 * has hydrated and with JavaScript switched off entirely. Hydration only adds
 * the pending state and the inline confirmation.
 */
export function AddToCart({
  skuId,
  back,
  max,
}: {
  skuId: string;
  /** Where to return the buyer after signing in, if the session has lapsed. */
  back: string;
  max: number;
}) {
  const [state, formAction] = useActionState(
    addToCartAction,
    {} as AddToCartState,
  );

  return (
    <div className="space-y-3">
      <form action={formAction} className="flex flex-wrap items-end gap-3">
        <input type="hidden" name="sku_id" value={skuId} />
        <input type="hidden" name="back" value={back} />

        <div className="space-y-1.5">
          <Label htmlFor="quantity" className="text-xs opacity-70">
            Quantity
          </Label>
          <Input
            id="quantity"
            name="quantity"
            type="number"
            defaultValue={1}
            min={1}
            max={Math.min(max, 20)}
            className="bg-background h-11 w-20 rounded-xl border-0 px-4"
          />
        </div>

        <SubmitButton />
      </form>

      {state.error && (
        <p
          role="alert"
          className="text-ink-rose flex items-center gap-1.5 text-sm font-medium"
        >
          <AlertCircle className="size-4" aria-hidden />
          {state.error}
        </p>
      )}

      {state.added && (
        <p
          // Announced politely so a screen reader hears the result without
          // losing the buyer's place on the page.
          aria-live="polite"
          className="flex items-center gap-1.5 text-sm font-medium"
        >
          <Check className="text-ink-mint size-4" aria-hidden />
          Added to your cart.{" "}
          <Link href="/cart" className="underline underline-offset-4">
            View cart
          </Link>
        </p>
      )}
    </div>
  );
}
