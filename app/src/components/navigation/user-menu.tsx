import { Menu } from "@base-ui/react/menu";
import { useNavigate } from "@tanstack/react-router";
import { LogOut } from "lucide-react";
import { useLogout, useSession } from "@/hooks/use-auth";
import { cn } from "@/lib/cn";

const initials = (name: string, email: string) => {
  const source = name?.trim() || email || "?";
  const parts = source.split(/\s+/).filter(Boolean);
  const [first, second] = parts;
  if (first && second) return `${first[0]}${second[0]}`.toUpperCase();
  return source.slice(0, 2).toUpperCase();
};

export const UserMenu = ({ compact = false }: { compact?: boolean }) => {
  const navigate = useNavigate();
  const { data } = useSession();
  const logout = useLogout();
  const user = data?.user;

  if (!user) return null;

  const onSignOut = async () => {
    await logout.mutateAsync();
    navigate({ to: "/login", replace: true });
  };

  return (
    <Menu.Root>
      <Menu.Trigger
        className={cn(
          compact
            ? "mx-auto mb-1 flex size-8 items-center justify-center rounded-full text-left hover:bg-background focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            : "flex w-full items-center gap-2.5 border-t border-border p-3 text-left hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
        title={user.display_name || user.email}
      >
        <div className="flex size-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
          {initials(user.display_name, user.email)}
        </div>
        {!compact && (
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-sm font-medium text-foreground">
              {user.display_name || user.email}
            </span>
            <span className="truncate text-xs text-muted-foreground">{user.email}</span>
          </div>
        )}
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner
          align={compact ? "start" : "center"}
          side={compact ? "right" : "top"}
          sideOffset={compact ? 10 : 6}
          className="z-50"
        >
          <Menu.Popup className="min-w-52 rounded-md border border-border bg-popover p-1 text-sm focus:outline-none">
            <Menu.Item
              onClick={onSignOut}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-destructive outline-none",
                "data-[highlighted]:bg-accent",
              )}
            >
              <LogOut className="size-4" />
              <span>Sign out</span>
            </Menu.Item>
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
};
