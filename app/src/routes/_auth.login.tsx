import { useForm } from "@tanstack/react-form";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { toast } from "sonner";
import { ApiUnreachable } from "@/components/status/api-unreachable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
  defaultLoginFormValues,
  loginBodyFromValues,
  validateEmail,
  validateLoginFormValues,
  validatePassword,
} from "@/features/auth/auth-form-state";
import { useInstanceSetupStatus } from "@/features/onboarding/use-instance-setup-status";
import { useLogin } from "@/hooks/use-auth";
import { errorText, firstString, submitWith } from "@/lib/form";

type LoginSearch = {
  from?: string;
};

export const Route = createFileRoute("/_auth/login")({
  validateSearch: (search: Record<string, unknown>): LoginSearch => {
    const from = safeReturnPath(search.from);
    return from ? { from } : {};
  },
  component: () => <LoginPage />,
});

const safeReturnPath = (value: unknown) => {
  if (typeof value !== "string") return undefined;
  if (!value.startsWith("/") || value.startsWith("//")) return undefined;
  if (value.startsWith("/login") || value.startsWith("/setup")) return undefined;
  return value;
};

const LoginPage = () => {
  const navigate = useNavigate();
  const { from } = Route.useSearch();
  const login = useLogin();
  const setup = useInstanceSetupStatus();
  const form = useForm({
    defaultValues: defaultLoginFormValues(),
    validators: {
      onSubmit: ({ value }) => validateLoginFormValues(value),
    },
    onSubmit: async ({ value }) => {
      try {
        await login.mutateAsync(loginBodyFromValues(value));
        navigate({ to: from ?? "/", replace: true });
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Login failed");
      }
    },
  });

  useEffect(() => {
    if (setup.loading || setup.error) return;
    if (setup.needsAdminSetup) {
      navigate({ to: "/setup", replace: true });
      return;
    }
    if (!setup.session) return;
    if (setup.requiresOnboarding && !setup.complete) {
      navigate({ to: "/onboarding", replace: true });
      return;
    }
    navigate({ to: from ?? "/overview", replace: true });
  }, [
    from,
    navigate,
    setup.complete,
    setup.error,
    setup.loading,
    setup.needsAdminSetup,
    setup.requiresOnboarding,
    setup.session,
  ]);

  if (setup.loading || setup.needsAdminSetup || setup.session) {
    return (
      <div className="flex min-h-[240px] w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (setup.error) {
    return <ApiUnreachable error={setup.error} variant="card" />;
  }

  return (
    <div className="w-full max-w-sm rounded-xl border border-border bg-card p-6">
      <div className="mb-5 flex flex-col gap-1">
        <h1 className="font-semibold text-lg tracking-tight">Sign in</h1>
        <p className="text-sm text-muted-foreground">
          Manage your collections, documents, and API keys.
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
              placeholder="admin@example.com"
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
              autoComplete="current-password"
              error={errorText(field.state.meta.errors)}
              label="Password"
              minLength={8}
              onBlur={field.handleBlur}
              onChange={(e) => field.handleChange(e.target.value)}
              placeholder="Password"
              required
              type="password"
              value={field.state.value}
            />
          )}
        </form.Field>
        <Button type="submit" disabled={login.isPending} size="lg">
          {login.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
};
