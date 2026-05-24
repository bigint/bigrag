import { Save } from "lucide-react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ProfileFormValues } from "@/features/settings/account-form-state";
import type { CurrentUser } from "@/hooks/use-auth";

const initials = (name: string, email: string) => {
  const source = name?.trim() || email || "?";
  const parts = source.split(/\s+/).filter(Boolean);
  const [first, second] = parts;
  if (first && second) return `${first[0]}${second[0]}`.toUpperCase();
  return source.slice(0, 2).toUpperCase();
};

interface AccountProfileSectionProps {
  readonly changed: boolean;
  readonly error: string | null;
  readonly onFieldChange: (field: keyof ProfileFormValues, value: string) => void;
  readonly onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  readonly saving: boolean;
  readonly user: CurrentUser | undefined;
  readonly values: ProfileFormValues;
}

export const AccountProfileSection = ({
  changed,
  error,
  onFieldChange,
  onSubmit,
  saving,
  user,
  values,
}: AccountProfileSectionProps) => {
  const displayName = user?.display_name || user?.email?.split("@")[0] || "—";
  const displayNameError = error?.startsWith("Display name") ? error : null;
  const emailError = error && !displayNameError ? error : null;

  return (
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
          <p className="mt-1 text-sm text-muted-foreground">Edit your operator profile.</p>
        </div>
      </div>
      <form className="mt-5 flex flex-col gap-4" noValidate onSubmit={onSubmit}>
        {error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          <Input
            autoComplete="name"
            error={displayNameError}
            label="Display name"
            maxLength={120}
            onChange={(event) => onFieldChange("displayName", event.target.value)}
            placeholder="Display name"
            value={values.displayName}
          />
          <Input
            autoComplete="email"
            description="Used for sign in and audit attribution."
            error={emailError}
            label="Email"
            onChange={(event) => onFieldChange("email", event.target.value)}
            placeholder="admin@example.com"
            required
            type="email"
            value={values.email}
          />
        </div>
        <div className="flex justify-end pt-1">
          <Button disabled={!user || !changed || saving} type="submit">
            <Save className="size-3.5" />
            {saving ? "Saving…" : "Save profile"}
          </Button>
        </div>
      </form>
    </section>
  );
};
