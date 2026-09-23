"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { Heart, ShoppingBag } from "lucide-react";

import { Button } from "@/components/ui/button";
import { addToCartAction, type AddToCartState } from "@/lib/cart-actions";
import {
  toggleFavouriteAction,
  type FavouriteState,
} from "@/lib/favourite-actions";

function IconSubmit({
  label,
  pendingLabel,
  children,
  className,
}: {
  label: string;
  pendingLabel: string;
  children: React.ReactNode;
  className?: string;
}) {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      variant="ghost"
      size="icon"
      disabled={pending}
      aria-label={pending ? pendingLabel : label}
      className={`bg-background/85 size-8 rounded-full backdrop-blur transition hover:scale-105 ${className ?? ""}`}
    >
      {children}
    </Button>
  );
}

/**
 * The two things worth doing from a card: save it, or put it in the basket.
 *
 * Each is its own form rather than one with two buttons, because they are
 * genuinely different actions and a card is not a checkout — there is no
 * "buy now" here, since that is only these two steps with a redirect, and a
 * third control would crowd a card that is mostly photograph.
 */
export function CardActions({
  skuId,
  slug,
  saved,
  inStock,
}: {
  skuId: string;
  slug: string;
  saved: boolean;
  inStock: boolean;
}) {
  const [, favouriteAction] = useActionState(
    toggleFavouriteAction,
    {} as FavouriteState,
  );
  const [cartState, cartAction] = useActionState(
    addToCartAction,
    {} as AddToCartState,
  );

  return (
    <div className="absolute top-3 right-3 flex flex-col gap-2">
      <form action={favouriteAction}>
        <input type="hidden" name="slug" value={slug} />
        <input type="hidden" name="saved" value={String(saved)} />
        <IconSubmit
          label={saved ? "Remove from saved" : "Save this piece"}
          pendingLabel="Saving…"
        >
          <Heart
            className={`size-4 ${saved ? "fill-ink-rose text-ink-rose" : ""}`}
            aria-hidden
          />
        </IconSubmit>
      </form>

      {inStock && (
        <form action={cartAction}>
          <input type="hidden" name="sku_id" value={skuId} />
          <input type="hidden" name="quantity" value="1" />
          <input type="hidden" name="back" value={`/products/${slug}`} />
          <IconSubmit
            label={cartState.added ? "In your cart" : "Add to cart"}
            pendingLabel="Adding…"
            className={cartState.added ? "bg-ink-mint text-background" : ""}
          >
            <ShoppingBag className="size-4" aria-hidden />
          </IconSubmit>
        </form>
      )}
    </div>
  );
}
