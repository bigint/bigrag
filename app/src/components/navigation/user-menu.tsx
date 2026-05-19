import { Button, cn, Menu, MenuItem, MenuSeparator, ThemeControl } from "@atelier/ui";
import { useNavigate } from "@tanstack/react-router";
import { LogOut } from "lucide-react";
import { useLogout, useSession } from "@/hooks/use-auth";

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
    <Menu
      align={compact ? "start" : "center"}
      popupStyle={compact ? undefined : { width: "calc(var(--anchor-width) - 1rem)" }}
      side={compact ? "right" : "top"}
      sideOffset={compact ? 10 : 6}
      trigger={
        <Button
          className={cn(
            compact
              ? "mx-auto mb-1 size-8 rounded-full p-0 text-left hover:bg-background"
              : "h-auto w-full justify-start gap-2.5 rounded-none border-border border-t p-3 text-left",
          )}
          title={user.display_name || user.email}
          variant="ghost"
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
        </Button>
      }
    >
      <div className="flex items-center justify-between gap-3 px-2 py-1.5">
        <span className="text-xs font-semibold text-muted-foreground">Theme</span>
        <ThemeControl className="shrink-0" />
      </div>
      <MenuSeparator />
      <MenuItem className="text-destructive" onClick={onSignOut}>
        <LogOut className="size-4" />
        <span>Sign out</span>
      </MenuItem>
    </Menu>
  );
};
