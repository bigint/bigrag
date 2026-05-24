import { useForm, useStore } from "@tanstack/react-form";
import { useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import {
  defaultPasswordFormValues,
  defaultProfileFormValues,
  passwordBodyFromValues,
  profileBodyFromValues,
  profileFormHasChanges,
  profileFormValuesFromUser,
  validatePasswordFormValues,
  validateProfileFormValues,
} from "@/features/settings/account-form-state";
import { AccountActiveSessionsSection } from "@/features/settings/tabs/account-active-sessions-section";
import { AccountProfileSection } from "@/features/settings/tabs/account-profile-section";
import {
  useChangePassword,
  useLogout,
  useLogoutAll,
  useSession,
  useUpdateCurrentUserProfile,
} from "@/hooks/use-auth";
import { errorText, firstString, submitWith } from "@/lib/form";

export const AccountTab = () => {
  const navigate = useNavigate();
  const { data: session } = useSession();
  const updateProfile = useUpdateCurrentUserProfile();
  const changePassword = useChangePassword();
  const logout = useLogout();
  const logoutAll = useLogoutAll();
  const [profileValues, setProfileValues] = useState(defaultProfileFormValues);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [signOutAllOpen, setSignOutAllOpen] = useState(false);
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
  const userDisplayName = user?.display_name ?? "";
  const userEmail = user?.email ?? "";
  const userId = user?.id;
  const savedProfileValues = user ? profileFormValuesFromUser(user) : defaultProfileFormValues();
  const profileChanged = user ? profileFormHasChanges(savedProfileValues, profileValues) : false;

  useEffect(() => {
    if (!userId) return;
    setProfileValues({
      displayName: userDisplayName,
      email: userEmail,
    });
    setProfileError(null);
  }, [userId, userDisplayName, userEmail]);

  const setProfileField = (field: keyof typeof profileValues, value: string) => {
    setProfileValues((current) => ({ ...current, [field]: value }));
    setProfileError(null);
  };

  const submitProfile = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user) return;
    const error = validateProfileFormValues(profileValues);
    if (error) {
      setProfileError(error);
      return;
    }
    try {
      await updateProfile.mutateAsync({
        id: user.id,
        ...profileBodyFromValues(profileValues),
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  const confirmSignOutEverywhere = async () => {
    try {
      await logoutAll.mutateAsync();
      setSignOutAllOpen(false);
      navigate({ to: "/login", replace: true });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <AccountProfileSection
        changed={profileChanged}
        error={profileError}
        onFieldChange={setProfileField}
        onSubmit={submitProfile}
        saving={updateProfile.isPending}
        user={user ?? undefined}
        values={profileValues}
      />

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

        <AccountActiveSessionsSection
          onSignOutEverywhere={() => setSignOutAllOpen(true)}
          pending={logoutAll.isPending}
        />
      </section>
      <ConfirmDialog
        open={signOutAllOpen}
        onClose={() => setSignOutAllOpen(false)}
        onConfirm={confirmSignOutEverywhere}
        title="Sign out everywhere"
        description="Sign out of every device? You'll need to log in again everywhere, including this one."
        confirmLabel="Sign out"
        loading={logoutAll.isPending}
      />
    </div>
  );
};
