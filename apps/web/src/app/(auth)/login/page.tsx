import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { loginAction } from "@/lib/auth-actions";
import { getCurrentUser } from "@/lib/api";

export const metadata = { title: "Sign in — Poshra" };

export default async function LoginPage() {
  if (await getCurrentUser()) redirect("/dashboard");

  return (
    <div className="bg-tint-lilac rounded-panel stitched w-full p-7 sm:p-9">
      <h1 className="text-3xl font-extrabold tracking-tight">Welcome back.</h1>
      <p className="mt-2 text-sm opacity-70">
        Sign in to manage your listings and orders.
      </p>

      <div className="mt-7">
        <AuthForm action={loginAction} submitLabel="Sign in" />
      </div>

      <p className="mt-7 text-center text-sm opacity-70">
        New here?{" "}
        <Link
          href="/register"
          className="font-semibold underline underline-offset-4"
        >
          Create an account
        </Link>
      </p>
    </div>
  );
}
