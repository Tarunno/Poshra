/**
 * Credentials a shopper hands to an AI agent.
 *
 * The value of a token exists for exactly one render: it comes back from the
 * mint call, is shown once, and is never stored anywhere — not in the
 * database, not in a cookie, not in this module. If the shopper loses it they
 * make another one, which is the same bargain GitHub and every other issuer of
 * long-lived tokens strikes, and for the same reason.
 */
import { apiFetch } from "./api";

export type AgentToken = {
  id: string;
  label: string;
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  active: boolean;
};

export async function listAgentTokens(): Promise<AgentToken[]> {
  try {
    const response = await apiFetch("/agent-tokens");
    if (!response.ok) return [];
    const body = (await response.json()) as { results?: AgentToken[] };
    return body.results ?? [];
  } catch {
    return [];
  }
}
