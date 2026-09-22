"use server";

/**
 * Server Actions for auth.
 *
 * These run on the server, so the password never touches client JavaScript and
 * the Set-Cookie headers from Django are passed straight to the browser.
 * A Server Action is a public POST endpoint, so every input is validated here.
 */
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const API_BASE =
  process.env.API_BASE_URL ?? "http://localhost:8080/api/marketplace";

export type AuthState = { error?: string };

/** Copies Django's auth cookies onto this response. */
async function storeCookies(response: Response) {
  const jar = await cookies();
  for (const raw of response.headers.getSetCookie()) {
    const [pair, ...attrs] = raw.split(";");
    const index = pair.indexOf("=");
    const name = pair.slice(0, index).trim();
    const value = pair.slice(index + 1).trim();
    const options: Record<string, unknown> = { path: "/" };
    for (const attr of attrs) {
      const [key, val] = attr.split("=").map((s) => s.trim());
      const k = key.toLowerCase();
      if (k === "httponly") options.httpOnly = true;
      else if (k === "secure") options.secure = true;
      else if (k === "path") options.path = val;
      else if (k === "samesite") options.sameSite = val.toLowerCase();
      else if (k === "max-age") options.maxAge = Number(val);
    }
    jar.set(name, value, options);
  }
}

export async function loginAction(
  _prev: AuthState,
  formData: FormData,
): Promise<AuthState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  if (!email || !password) return { error: "Email and password are required." };

  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    return { error: body.detail ?? "Could not sign in." };
  }
  await storeCookies(response);
  redirect("/dashboard");
}

export async function registerAction(
  _prev: AuthState,
  formData: FormData,
): Promise<AuthState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const fullName = String(formData.get("full_name") ?? "").trim();
  const role = String(formData.get("role") ?? "buyer");

  if (!email || !password) return { error: "Email and password are required." };
  if (password.length < 12)
    return { error: "Use at least 12 characters for your password." };
  if (role !== "buyer" && role !== "artisan")
    return { error: "Choose buyer or artisan." };

  const response = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: fullName, role }),
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    return { error: body.detail ?? "Could not create the account." };
  }
  // Registration does not sign you in; log in through the normal path.
  return loginAction({}, formData);
}

export async function logoutAction(): Promise<void> {
  const jar = await cookies();
  const csrf = jar.get(process.env.CSRF_COOKIE_NAME ?? "poshra_csrf")?.value;
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    headers: {
      cookie: jar.toString(),
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    cache: "no-store",
  }).catch(() => undefined);

  for (const name of ["poshra_at", "poshra_rt", "poshra_csrf"])
    jar.delete(name);
  redirect("/");
}
