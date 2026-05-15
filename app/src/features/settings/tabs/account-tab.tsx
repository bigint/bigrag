import { useForm, useStore } from "@tanstack/react-form";
import { useNavigate } from "@tanstack/react-router";
import { LogOut, ShieldAlert, UserRound } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  defaultPasswordFormValues,
  passwordBodyFromValues,
  validatePasswordFormValues,
} from "@/features/settings/account-form-state";
import { useChangePassword, useLogout, useLogoutAll, useSession } from "@/hooks/use-auth";
import { errorText, firstString, submitWith } from "@/lib/form";

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
  const form = useForm({
    defaultValues: defaultPasswordFormValues(),
    validators: {
      onSubmit: ({ value }) => validatePasswordFormValues(value),
    },
    onSubmit: async ({ value }) => {
      try {
        await changePassword.mutateAsync(passwordBodyFromValues(value));
        toast.success("Password updated");
        await logout.mutateAsync();
        navigate({ to: "/login", replace: true });
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed");
      }
    },
  });
  const values = useStore(form.store, (state) => state.values);

  const user = session?.user;
  const displayName = user?.display_name || user?.email?.split("@")[0] || "—";

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
    <div className="flex flex-col gap-4">
      <section className="rounded-md border border-border bg-card p-4">
        <div className="flex flex-wrap items-start gap-4">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
            {user ? initials(user.display_name, user.email) : "—"}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="truncate text-base font-semibold tracking-normal">{displayName}</h3>
              {user?.role && (
                <span className="rounded-full bg-muted px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {user.role}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Profile details are managed by the current admin account.
            </p>
          </div>
        </div>
        <dl className="mt-5 grid gap-3">
          <AccountDetail icon={<UserRound className="size-4" />} label="Display name">
            {user?.display_name || displayName}
          </AccountDetail>
          <AccountDetail label="Email">{user?.email ?? "—"}</AccountDetail>
        </dl>
      </section>

      <section className="rounded-md border border-border bg-card p-4">
        <div>
          <h3 className="text-base font-semibold tracking-normal">Password</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Updating your password signs this browser out after the change is saved.
          </p>
        </div>
        <form
          className="mt-4 flex flex-col gap-4"
          noValidate
          onSubmit={submitWith(() => form.handleSubmit())}
        >
          <form.Subscribe selector={(state) => state.errors}>
            {(errors) => {
              const formError = firstString(errors);
              return formError ? (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              ) : null;
            }}
          </form.Subscribe>
          <form.Field
            name="current"
            validators={{
              onSubmit: ({ value }) => (value ? undefined : "Current password is required"),
            }}
          >
            {(field) => (
              <Input
                autoComplete="current-password"
                error={errorText(field.state.meta.errors)}
                label="Current password"
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                placeholder="Current password"
                required
                type="password"
                value={field.state.value}
              />
            )}
          </form.Field>
          <div className="grid gap-4">
            <form.Field
              name="next"
              validators={{
                onSubmit: ({ value }) =>
                  value
                    ? value.length < 8
                      ? "New password must be at least 8 characters"
                      : undefined
                    : "New password is required",
              }}
            >
              {(field) => (
                <Input
                  autoComplete="new-password"
                  description="At least 8 characters."
                  error={errorText(field.state.meta.errors)}
                  label="New password"
                  minLength={8}
                  onBlur={field.handleBlur}
                  onChange={(e) => field.handleChange(e.target.value)}
                  placeholder="New password"
                  required
                  type="password"
                  value={field.state.value}
                />
              )}
            </form.Field>
            <form.Field
              name="confirm"
              validators={{
                onSubmit: ({ value }) =>
                  value
                    ? value.length < 8
                      ? "Confirm new password must be at least 8 characters"
                      : undefined
                    : "Confirm new password is required",
              }}
            >
              {(field) => (
                <Input
                  autoComplete="new-password"
                  error={
                    errorText(field.state.meta.errors) ??
                    (values.confirm && values.next !== values.confirm ? "Doesn't match" : null)
                  }
                  label="Confirm new password"
                  minLength={8}
                  onBlur={field.handleBlur}
                  onChange={(e) => field.handleChange(e.target.value)}
                  placeholder="Confirm new password"
                  required
                  type="password"
                  value={field.state.value}
                />
              )}
            </form.Field>
          </div>
          <div className="flex justify-end pt-1">
            <Button type="submit" disabled={changePassword.isPending}>
              {changePassword.isPending ? "Updating…" : "Update password"}
            </Button>
          </div>
        </form>

        <div className="mt-5 border-border border-t pt-4">
          <h3 className="flex items-center gap-2 text-base font-semibold tracking-normal">
            <ShieldAlert className="size-3.5 text-warning" />
            Active sessions
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Sign out of every browser or device where this account is logged in.
          </p>
          <div className="mt-4 flex flex-col gap-3 rounded-md border border-border bg-muted/25 p-3">
            <p className="text-sm text-muted-foreground">
              This revokes all refresh tokens immediately. You'll need to log in again on every
              device, including this one.
            </p>
            <Button
              className="shrink-0"
              variant="outline"
              disabled={logoutAll.isPending}
              onClick={signOutEverywhere}
            >
              <LogOut className="size-3.5" />
              {logoutAll.isPending ? "Signing out…" : "Sign out everywhere"}
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
};

const AccountDetail = ({
  children,
  icon,
  label,
}: {
  readonly children: React.ReactNode;
  readonly icon?: React.ReactNode;
  readonly label: string;
}) => (
  <div className="rounded-md border border-border bg-muted/25 p-3">
    <dt className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      {icon}
      {label}
    </dt>
    <dd className="mt-2 truncate text-sm font-semibold text-foreground">{children}</dd>
  </div>
);
