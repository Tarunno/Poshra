"use client";

import { useActionState, useState } from "react";
import { useFormStatus } from "react-dom";
import { AlertCircle, Eye, EyeOff, ShoppingBag } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MakersHand } from "@/components/motifs";
import type { AuthState } from "@/lib/auth-actions";

const field = "bg-background rounded-xl border-0 h-11 px-4";

function SubmitButton({ label }: { label: string }) {
  // Pending state comes from the form itself, so there is no manual flag to
  // keep in sync.
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      size="lg"
      className="mt-2 w-full rounded-full"
      disabled={pending}
    >
      {pending ? "Please wait…" : label}
    </Button>
  );
}

/** A role choice styled as a card; the radio stays the real control. */
function RoleOption({
  value,
  title,
  hint,
  icon: Icon,
  defaultChecked,
}: {
  value: string;
  title: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
  defaultChecked?: boolean;
}) {
  return (
    <label className="cursor-pointer">
      <input
        type="radio"
        name="role"
        value={value}
        defaultChecked={defaultChecked}
        className="peer sr-only"
      />
      <span className="bg-background/50 peer-checked:bg-background peer-focus-visible:ring-foreground/40 flex h-full flex-col gap-1 rounded-2xl p-4 ring-2 ring-transparent transition peer-checked:ring-current peer-focus-visible:ring-offset-2">
        <Icon className="size-5" />
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-xs opacity-70">{hint}</span>
      </span>
    </label>
  );
}

type Props = {
  action: (state: AuthState, formData: FormData) => Promise<AuthState>;
  submitLabel: string;
  showName?: boolean;
  showRole?: boolean;
  /** Where to go after signing in, when the visitor was sent here mid-task. */
  next?: string;
};

export function AuthForm({
  action,
  submitLabel,
  showName,
  showRole,
  next,
}: Props) {
  const [state, formAction] = useActionState(action, {} as AuthState);
  const [visible, setVisible] = useState(false);

  return (
    <form action={formAction} className="space-y-5">
      {next && <input type="hidden" name="next" value={next} />}
      {state?.error && (
        <Alert variant="destructive" className="rounded-2xl">
          <AlertCircle className="size-4" />
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}

      {showName && (
        <div className="space-y-2">
          <Label htmlFor="full_name">Full name</Label>
          <Input
            className={field}
            id="full_name"
            name="full_name"
            autoComplete="name"
            placeholder="Rina Akter"
          />
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          className={field}
          id="email"
          name="email"
          type="email"
          required
          autoComplete="email"
          placeholder="you@example.com"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <div className="relative">
          <Input
            className={`${field} pr-12`}
            id="password"
            name="password"
            type={visible ? "text" : "password"}
            required
            autoComplete={showName ? "new-password" : "current-password"}
            minLength={showName ? 12 : undefined}
          />
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            className="absolute inset-y-0 right-3 grid place-items-center opacity-60 hover:opacity-100"
            aria-label={visible ? "Hide password" : "Show password"}
          >
            {visible ? (
              <EyeOff className="size-4" />
            ) : (
              <Eye className="size-4" />
            )}
          </button>
        </div>
        {showName && (
          <p className="text-xs opacity-60">At least 12 characters.</p>
        )}
      </div>

      {showRole && (
        <fieldset className="space-y-2">
          <legend className="mb-2 text-sm font-medium">I want to</legend>
          <div className="grid grid-cols-2 gap-3">
            <RoleOption
              value="buyer"
              title="Buy crafts"
              hint="Browse and order handmade work"
              icon={ShoppingBag}
              defaultChecked
            />
            <RoleOption
              value="artisan"
              title="Sell my work"
              hint="List what you make"
              icon={MakersHand}
            />
          </div>
        </fieldset>
      )}

      <SubmitButton label={submitLabel} />
    </form>
  );
}
