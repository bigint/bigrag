import { useForm } from "@tanstack/react-form";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { toast } from "sonner";
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
import { useLogin, useSetupStatus } from "@/hooks/use-auth";
import { errorText, firstString, submitWith } from "@/lib/form";

export const Route = createFileRoute("/_auth/login")({
  validateSearch: (search: Record<string, unknown>) => ({
    from: safeReturnPath(search.from),
  }),
  component: () => <LoginPage />,
});

const safeReturnPath = (value: unknown) => {
  if (typeof value !== "string") return undefined;
  if (!value.startsWith("/") || value.startsWith("//")) return undefined;
  if (value.startsWith("/login") || value.startsWith("/setup")) return undefined;
  return value;
};

const useRedirectIfSetupNeeded = (needsSetup: boolean | undefined) => {
  const navigate = useNavigate();
  useEffect(() => {
    if (needsSetup) navigate({ to: "/setup", replace: true });
  }, [needsSetup, navigate]);
};

const LoginPage = () => {
  const navigate = useNavigate();
  const { from } = Route.useSearch();
  const login = useLogin();
  const { data: setupStatus, isPending, isError, error } = useSetupStatus();
  const form = useForm({
    defaultValues: defaultLoginFormValues(),
    validators: {
      onSubmit: ({ value }) => validateLoginFormValues(value),
    },
    onSubmit: async ({ value }) => {
      try {
        await login.mutateAsync(loginBodyFromValues(value));
        if (from) {
          window.location.assign(from);
        } else {
          navigate({ to: "/overview", replace: true });
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Login failed");
      }
    },
  });

  useRedirectIfSetupNeeded(setupStatus?.needs_setup);

  if (isPending || setupStatus?.needs_setup) {
    return (
      <div className="flex min-h-[240px] w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="w-full max-w-sm rounded-xl border border-destructive/40 bg-card p-6">
        <h1 className="font-semibold text-base">Can't reach bigRAG</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
        {import.meta.env.DEV ? (
          <p className="mt-3 text-xs text-muted-foreground">
            Make sure the bigRAG server is running and{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono">VITE_BIGRAG_URL</code> points
            to the API.
          </p>
        ) : (
          <p className="mt-3 text-xs text-muted-foreground">
            The bigRAG API is not reachable. Try again in a moment, or contact your administrator.
          </p>
        )}
      </div>
    );
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
