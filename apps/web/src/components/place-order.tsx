"use client";

import Link from "next/link";
import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { AlertCircle, CreditCard, Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { placeOrderAction, type PlaceOrderState } from "@/lib/order-actions";

function SubmitButton({ total }: { total: string }) {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      size="lg"
      className="w-full rounded-full"
      disabled={pending}
    >
      <Lock className="size-4" aria-hidden />
      {pending ? "Placing your order…" : `Pay ${total}`}
    </Button>
  );
}

/** A test outcome, styled as a card choice; the radio stays the real control. */
function Outcome({
  value,
  title,
  hint,
  defaultChecked,
}: {
  value: string;
  title: string;
  hint: string;
  defaultChecked?: boolean;
}) {
  return (
    <label className="cursor-pointer">
      <input
        type="radio"
        name="outcome"
        value={value}
        defaultChecked={defaultChecked}
        className="peer sr-only"
      />
      <span className="bg-background/50 peer-checked:bg-background peer-focus-visible:ring-foreground/40 flex h-full flex-col gap-1 rounded-2xl p-4 ring-2 ring-transparent transition peer-checked:ring-current peer-focus-visible:ring-offset-2">
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-xs opacity-70">{hint}</span>
      </span>
    </label>
  );
}

/**
 * The payment step.
 *
 * The key is minted when the page renders and travels in a hidden field, so a
 * double click or a refreshed POST carries the same one and checkout replays
 * its first answer rather than charging twice.
 */
export function PlaceOrder({
  idempotencyKey,
  total,
}: {
  idempotencyKey: string;
  total: string;
}) {
  const [state, formAction] = useActionState(
    placeOrderAction,
    {} as PlaceOrderState,
  );

  return (
    <form action={formAction} className="space-y-5">
      <input type="hidden" name="idempotency_key" value={idempotencyKey} />

      <div className="flex items-center gap-2 text-sm font-semibold">
        <CreditCard className="size-4" aria-hidden />
        Payment
      </div>

      <p className="text-xs leading-relaxed opacity-70">
        Payments are simulated. A real processor returns a token from its own
        SDK, so card details never reach Poshra&rsquo;s servers — choosing an
        outcome here stands in for that exchange.
      </p>

      <fieldset>
        <legend className="sr-only">Test payment outcome</legend>
        <div className="grid grid-cols-2 gap-3">
          <Outcome
            value="approve"
            title="Approve"
            hint="The order is confirmed"
            defaultChecked
          />
          <Outcome
            value="decline"
            title="Decline"
            hint="The hold on stock is released"
          />
        </div>
      </fieldset>

      {state.error && (
        <p
          role="alert"
          className="text-ink-rose flex items-start gap-1.5 text-sm font-medium"
        >
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {state.error}
            {state.backToCart && (
              <>
                {" "}
                <Link href="/cart" className="underline underline-offset-4">
                  Back to your cart
                </Link>
              </>
            )}
          </span>
        </p>
      )}

      <SubmitButton total={total} />
    </form>
  );
}
