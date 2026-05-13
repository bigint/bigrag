import { useNavigate } from "@tanstack/react-router";
import { LogOut, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useChangePassword, useLogout, useLogoutAll, useSession } from "@/hooks/use-auth";

const initials = (name: string, email: string) => {
  const source = name?.trim() || email || "?";
  const parts = source.split(/\s+/).filter(Boolean);
  const [first, second] = parts;
  if (first && second) return `${first[0]}${second[0]}`.toUpperCase();
  return source.slice(0, 2).toUpperCase();
};

export const AccountTab = () => {
  const navigate = useNavigate();
  const { data: session } = useSession();
  const changePassword = useChangePassword();
  const logout = useLogout();
  const logoutAll = useLogoutAll();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const user = session?.user;
  const displayName = user?.display_name || user?.email?.split("@")[0] || "—";

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (next !== confirm) {
      toast.error("Passwords do not match");
      return;
    }
    try {
      await changePassword.mutateAsync({ current_password: current, new_password: next });
      toast.success("Password updated");
      await logout.mutateAsync();
      navigate({ to: "/login", replace: true });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  const signOutEverywhere = async () => {
    if (!window.confirm("Sign out of every device? You'll need to log in again everywhere.")) {
      return;
    }
    try {
      await logoutAll.mutateAsync();
      navigate({ to: "/login", replace: true });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="rounded-md border border-border bg-card">
        <div className="flex items-center gap-4 border-b border-border bg-muted/35 p-4">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
            {user ? initials(user.display_name, user.email) : "—"}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold">{displayName}</div>
            <div className="truncate text-xs text-muted-foreground">{user?.email ?? "—"}</div>
          </div>
          {user?.role && (
            <span className="rounded-md border border-border bg-surface px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {user.role}
            </span>
          )}
        </div>
        <div className="grid gap-4 p-4 sm:grid-cols-2">
          <Input label="Display name" defaultValue={user?.display_name} disabled />
          <Input label="Email" defaultValue={user?.email} disabled />
        </div>
      </section>

      <section className="rounded-md border border-border bg-card xl:row-span-2">
        <header className="flex flex-col gap-1 border-b border-border bg-muted/35 p-4">
          <h3 className="text-sm font-semibold tracking-normal">Change password</h3>
          <p className="text-xs text-muted-foreground">
            You'll be signed out of all sessions after changing it.
          </p>
        </header>
        <form onSubmit={save} className="flex flex-col gap-4 p-4">
          <Input
            label="Current password"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="New password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={next}
              onChange={(e) => setNext(e.target.value)}
              description="At least 8 characters."
              required
            />
            <Input
              label="Confirm new password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              error={confirm && next !== confirm ? "Doesn't match" : null}
              required
            />
          </div>
          <div className="flex justify-end pt-1">
            <Button type="submit" disabled={changePassword.isPending}>
              {changePassword.isPending ? "Updating…" : "Update password"}
            </Button>
          </div>
        </form>
      </section>

      <section className="rounded-md border border-border bg-card">
        <header className="flex flex-col gap-1 border-b border-border bg-muted/35 p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold tracking-normal">
            <ShieldAlert className="size-3.5 text-warning" />
            Active sessions
          </h3>
          <p className="text-xs text-muted-foreground">
            Sign out of every browser or device where this account is logged in.
          </p>
        </header>
        <div className="flex items-center justify-between gap-4 p-4">
          <p className="text-xs text-muted-foreground">
            This revokes all refresh tokens immediately. You'll need to log in again on every
            device, including this one.
          </p>
          <Button variant="outline" disabled={logoutAll.isPending} onClick={signOutEverywhere}>
            <LogOut className="size-3.5" />
            {logoutAll.isPending ? "Signing out…" : "Sign out everywhere"}
          </Button>
        </div>
      </section>
    </div>
  );
};
