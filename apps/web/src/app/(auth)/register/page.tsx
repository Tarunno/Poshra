import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { registerAction } from "@/lib/auth-actions";
import { getCurrentUser } from "@/lib/api";

export const metadata = { title: "Join Poshra" };

export default async function RegisterPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  if (await getCurrentUser()) redirect("/dashboard");
  const { next } = await searchParams;

  return (
    <div className="bg-tint-saffron rounded-panel stitched w-full p-7 sm:p-9">
      <h1 className="text-3xl font-extrabold tracking-tight">Join Poshra.</h1>
      <p className="mt-2 text-sm opacity-70">
        Buy handmade crafts, or sell your own work worldwide. Free, with no
        listing fees.
      </p>

      <div className="mt-7">
        <AuthForm
          action={registerAction}
          submitLabel="Create account"
          showName
          showRole
          next={next}
        />
      </div>

      <p className="mt-7 text-center text-sm opacity-70">
        Already have an account?{" "}
        <Link
          href={next ? `/login?next=${encodeURIComponent(next)}` : "/login"}
          className="font-semibold underline underline-offset-4"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}
