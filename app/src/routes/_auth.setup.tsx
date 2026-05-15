import { useForm } from "@tanstack/react-form";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  defaultSetupFormValues,
  setupBodyFromValues,
  validateEmail,
  validatePassword,
  validateSetupFormValues,
} from "@/features/auth/auth-form-state";
import { useSetup, useSetupStatus } from "@/hooks/use-auth";
import { errorText, firstString, submitWith } from "@/lib/form";

export const Route = createFileRoute("/_auth/setup")({
  component: () => <SetupPage />,
});

const useRedirectIfSetupComplete = () => {
  const navigate = useNavigate();
  const { data: status, isPending } = useSetupStatus();
  useEffect(() => {
    if (!isPending && status && !status.needs_setup) navigate({ to: "/login", replace: true });
  }, [isPending, status, navigate]);
};

const SetupPage = () => {
  const navigate = useNavigate();
  const setup = useSetup();
  const form = useForm({
    defaultValues: defaultSetupFormValues(),
    validators: {
      onSubmit: ({ value }) => validateSetupFormValues(value),
    },
    onSubmit: async ({ value }) => {
      try {
        await setup.mutateAsync(setupBodyFromValues(value));
        toast.success("Admin account created");
        navigate({ to: "/overview", replace: true });
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Setup failed");
      }
    },
  });

  useRedirectIfSetupComplete();

  return (
    <div className="w-full max-w-md rounded-xl border border-border bg-card p-6">
      <div className="mb-5 flex flex-col gap-1">
        <div className="inline-flex items-center gap-2 self-start rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-accent-foreground">
          First-time setup
        </div>
        <h1 className="font-semibold text-lg tracking-tight">Create the first admin</h1>
        <p className="text-sm text-muted-foreground">
          This account owns the admin UI. You can invite more admins after signing in.
        </p>
      </div>
      <form
        className="flex flex-col gap-4"
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
        <form.Field name="displayName">
          {(field) => (
            <Input
              autoComplete="name"
              label="Display name"
              onBlur={field.handleBlur}
              onChange={(e) => field.handleChange(e.target.value)}
              placeholder="Ada Lovelace"
              value={field.state.value}
            />
          )}
        </form.Field>
        <form.Field
          name="email"
          validators={{
            onSubmit: ({ value }) => validateEmail(value),
          }}
        >
          {(field) => (
            <Input
              autoComplete="email"
              error={errorText(field.state.meta.errors)}
              label="Email"
              onBlur={field.handleBlur}
              onChange={(e) => field.handleChange(e.target.value)}
              required
              type="email"
              value={field.state.value}
            />
          )}
        </form.Field>
        <form.Field
          name="password"
          validators={{
            onSubmit: ({ value }) => validatePassword(value),
          }}
        >
          {(field) => (
            <Input
              autoComplete="new-password"
              description="At least 8 characters."
              error={errorText(field.state.meta.errors)}
              label="Password"
              minLength={8}
              onBlur={field.handleBlur}
              onChange={(e) => field.handleChange(e.target.value)}
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
                  ? "Confirm password must be at least 8 characters"
                  : undefined
                : "Confirm password is required",
          }}
        >
          {(field) => (
            <Input
              autoComplete="new-password"
              error={errorText(field.state.meta.errors)}
              label="Confirm password"
              minLength={8}
              onBlur={field.handleBlur}
              onChange={(e) => field.handleChange(e.target.value)}
              required
              type="password"
              value={field.state.value}
            />
          )}
        </form.Field>
        <Button type="submit" size="lg" disabled={setup.isPending}>
          {setup.isPending ? "Creating account…" : "Create admin & sign in"}
        </Button>
      </form>
    </div>
  );
};
