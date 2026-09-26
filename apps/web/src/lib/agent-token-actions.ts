"use server";

/**
 * Minting and revoking agent tokens.
 *
 * The minted value is returned to the page and shown once. It is deliberately
 * not put in a cookie or a redirect parameter on its way there: both are
 * places a credential outlives the moment it was needed.
 */
import { revalidatePath } from "next/cache";

import { apiWriteFetch } from "./api";

export type MintState = {
  /** Shown once, then gone. Absent on every render but the one after minting. */
  token?: string;
  label?: string;
  error?: string;
};

export async function mintAgentTokenAction(
  _prev: MintState,
  formData: FormData,
): Promise<MintState> {
  const label = String(formData.get("label") ?? "").trim();
  if (!label) return { error: "Give the token a name you will recognise." };

  const response = await apiWriteFetch("/agent-tokens", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ label }),
  });

  if (response.status === 401) return { error: "Sign in first." };
  if (response.status === 429) {
    return { error: "That is a lot of tokens at once. Try again in a minute." };
  }
  if (!response.ok) return { error: "That did not work. Try again." };

  const body = (await response.json()) as { token?: string };
  if (!body.token) return { error: "That did not work. Try again." };

  revalidatePath("/dashboard/agents");
  return { token: body.token, label };
}

export type RevokeState = { error?: string };

export async function revokeAgentTokenAction(
  _prev: RevokeState,
  formData: FormData,
): Promise<RevokeState> {
  const id = String(formData.get("id") ?? "");
  if (!id) return {};

  const response = await apiWriteFetch(
    `/agent-tokens/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
  if (!response.ok) return { error: "That did not revoke. Try again." };

  revalidatePath("/dashboard/agents");
  return {};
}
