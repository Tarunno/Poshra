import { redirect } from "next/navigation";

import { AgentTokens } from "@/components/agent-tokens";
import { KanthaRule } from "@/components/motifs";
import { getCurrentUser } from "@/lib/api";
import { listAgentTokens } from "@/lib/agent-tokens";

export const metadata = { title: "Assistants — Poshra" };

/**
 * The MCP endpoint a shopper pastes into their agent.
 *
 * It has to be the address the *browser* can reach, not the one inside the
 * cluster, because the thing that will call it is on their machine.
 */
const MCP_ENDPOINT =
  process.env.NEXT_PUBLIC_MCP_URL ?? "http://192.168.110.201/mcp";

export default async function AgentsPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/dashboard/agents");

  const tokens = await listAgentTokens();

  return (
    <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <header className="space-y-3">
        <p className="text-sm tracking-[0.14em] uppercase opacity-55">
          Assistants
        </p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Connect an AI assistant
        </h1>
        <KanthaRule />
      </header>

      <div className="mt-8">
        <AgentTokens tokens={tokens} endpoint={MCP_ENDPOINT} />
      </div>
    </main>
  );
}
