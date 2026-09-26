"use client";

import Link from "next/link";
import { Bot, Heart, LayoutDashboard, LogOut, Package } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { logoutAction } from "@/lib/auth-actions";
import type { User } from "@/lib/api";

/** Client Component: it needs interactivity, so it is kept as small as possible. */
export function UserMenu({ user }: { user: User }) {
  const initials = (user.full_name || user.email).slice(0, 2).toUpperCase();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="rounded-full"
          aria-label="Account menu"
        >
          <Avatar className="size-8">
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <p className="text-sm font-medium">
            {user.full_name || "Your account"}
          </p>
          <p className="text-muted-foreground truncate text-xs">{user.email}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/dashboard" className="cursor-pointer">
            <LayoutDashboard className="size-4" /> Dashboard
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/orders" className="cursor-pointer">
            <Package className="size-4" /> Your orders
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/saved" className="cursor-pointer">
            <Heart className="size-4" /> Saved pieces
          </Link>
        </DropdownMenuItem>
        {/* Where a shopper connects an AI assistant to their own account.
            It belongs beside the other account settings rather than in the
            header: it is something you set up once and rarely revisit. */}
        <DropdownMenuItem asChild>
          <Link href="/dashboard/agents" className="cursor-pointer">
            <Bot className="size-4" /> Assistants
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <form action={logoutAction}>
          <button type="submit" className="w-full">
            <DropdownMenuItem asChild>
              <span className="w-full cursor-pointer">
                <LogOut className="size-4" /> Sign out
              </span>
            </DropdownMenuItem>
          </button>
        </form>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
