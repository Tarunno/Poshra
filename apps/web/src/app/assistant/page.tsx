import { redirect } from "next/navigation";

import { ShoppingChat } from "@/components/shopping-chat";
import { getCurrentUser } from "@/lib/api";

export const metadata = { title: "Ask Poshra — Poshra" };

export default async function AssistantPage() {
  // The assistant costs money to answer, so it is not open to the world.
  if (!(await getCurrentUser())) redirect("/login?next=%2Fassistant");

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-extrabold tracking-tight">Ask Poshra</h1>
      <ShoppingChat />
    </div>
  );
}
