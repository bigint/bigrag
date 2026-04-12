"use client";

import { Menu } from "@base-ui/react/menu";
import { LogOut, Moon, Sun, SunMoon } from "lucide-react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { useLogout, useSession } from "@/hooks/use-auth";
import { useTheme } from "@/stores/theme";

const initials = (name: string, email: string) => {
  const source = name?.trim() || email || "?";
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0]![0]}${parts[1]![0]}`.toUpperCase();
  return source.slice(0, 2).toUpperCase();
};

export const UserMenu = () => {
  const router = useRouter();
  const { data } = useSession();
  const logout = useLogout();
  const { theme, setTheme } = useTheme();
  const user = data?.user;

  if (!user) return null;

  const onSignOut = async () => {
    await logout.mutateAsync();
    router.replace("/login");
  };

  return (
    <Menu.Root>
      <Menu.Trigger
        className={cn(
          "flex w-full items-center gap-2.5 rounded-md p-2 text-left transition-colors",
          "hover:bg-[var(--color-muted)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]",
        )}
      >
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-xs font-semibold text-white">
          {initials(user.display_name, user.email)}
        </div>
        <div className="flex min-w-0 flex-col">
          <span className="truncate text-sm font-medium text-[var(--color-foreground)]">
            {user.display_name || user.email}
          </span>
          <span className="truncate text-xs text-[var(--color-muted-foreground)]">
            {user.email}
          </span>
        </div>
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner align="start" side="top" sideOffset={6} className="z-50">
          <Menu.Popup className="min-w-[200px] rounded-md border border-[var(--color-border)] bg-[var(--color-popover)] p-1 text-sm shadow-[var(--shadow-md)] focus:outline-none">
            <div className="px-2 pb-1 pt-1.5 text-xs text-[var(--color-muted-foreground)]">
              Theme
            </div>
            <Menu.Item
              onClick={() => setTheme("light")}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 outline-none",
                "data-[highlighted]:bg-[var(--color-accent)] data-[highlighted]:text-[var(--color-accent-foreground)]",
              )}
            >
              <Sun className="h-4 w-4" />
              <span>Light</span>
              {theme === "light" && <span className="ml-auto text-xs">✓</span>}
            </Menu.Item>
            <Menu.Item
              onClick={() => setTheme("dark")}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 outline-none",
                "data-[highlighted]:bg-[var(--color-accent)] data-[highlighted]:text-[var(--color-accent-foreground)]",
              )}
            >
              <Moon className="h-4 w-4" />
              <span>Dark</span>
              {theme === "dark" && <span className="ml-auto text-xs">✓</span>}
            </Menu.Item>
            <Menu.Item
              onClick={() => setTheme("system")}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 outline-none",
                "data-[highlighted]:bg-[var(--color-accent)] data-[highlighted]:text-[var(--color-accent-foreground)]",
              )}
            >
              <SunMoon className="h-4 w-4" />
              <span>System</span>
              {theme === "system" && <span className="ml-auto text-xs">✓</span>}
            </Menu.Item>
            <Menu.Separator className="my-1 h-px bg-[var(--color-border)]" />
            <Menu.Item
              onClick={onSignOut}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-[var(--color-destructive)] outline-none",
                "data-[highlighted]:bg-[color-mix(in_oklab,var(--color-destructive),transparent_90%)]",
              )}
            >
              <LogOut className="h-4 w-4" />
              <span>Sign out</span>
            </Menu.Item>
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
};
